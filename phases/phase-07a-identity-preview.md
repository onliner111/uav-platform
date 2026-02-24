# Phase 07A Identity Preview - Composite Tenant Constraints

## Scope

This preview sub-phase is limited to:

- `users`
- `roles`
- `user_roles`

Out of scope for this preview:

- Any non-identity table
- Any Phase 07B module (`incidents`, `alerts`, `command_requests`)
- Changes to `phases/phase-07-tenant-boundary.md`

## Goals

- Enforce DB-level tenant boundary for user-role bindings.
- Ensure `user_roles` cannot link a `user` and `role` from different tenants.
- Keep API behavior unchanged for valid in-tenant operations.
- Return not-found style behavior for cross-tenant binding attempts.

## Composite PK Strategy for `user_roles`

### Target schema

- Add `tenant_id` column to `user_roles` (`NOT NULL` after backfill).
- Use composite primary key:
  - `(tenant_id, user_id, role_id)`
- Add composite foreign keys:
  - `(tenant_id, user_id) -> users (tenant_id, id)`
  - `(tenant_id, role_id) -> roles (tenant_id, id)`

### Parent key support

To support composite FK targets, add parent-side uniqueness:

- `users`: `UNIQUE (tenant_id, id)`
- `roles`: `UNIQUE (tenant_id, id)`

### Supporting indexes

- `user_roles (tenant_id, user_id)` for permission collection path.
- `user_roles (tenant_id, role_id)` for reverse membership queries and cleanup.

## Required Migrations (3-Step Plan)

### Step 1: Expand (non-breaking)

- Add `user_roles.tenant_id` as nullable.
- Add indexes:
  - `ix_user_roles_tenant_user (tenant_id, user_id)`
  - `ix_user_roles_tenant_role (tenant_id, role_id)`
- Add parent unique constraints:
  - `uq_users_tenant_id_id (tenant_id, id)`
  - `uq_roles_tenant_id_id (tenant_id, id)`

### Step 2: Backfill and Validate

- Backfill `user_roles.tenant_id` from trusted parent join.
  - Preferred source: `users.tenant_id` by `user_id`.
  - Validation: `users.tenant_id == roles.tenant_id` for every link row.
- Fail migration if any mismatch is found.
- Emit clear mismatch output to support remediation before retry.

### Step 3: Enforce

- Set `user_roles.tenant_id` to `NOT NULL`.
- Drop legacy FKs:
  - `user_roles.user_id -> users.id`
  - `user_roles.role_id -> roles.id`
- Add composite FKs:
  - `(tenant_id, user_id) -> users(tenant_id, id)`
  - `(tenant_id, role_id) -> roles(tenant_id, id)`
- Replace legacy PK `(user_id, role_id)` with composite PK `(tenant_id, user_id, role_id)`.

## IdentityService Updates

Target file: `app/services/identity_service.py`

### Methods requiring updates

- `bootstrap_admin`
  - Insert `UserRole(tenant_id=payload.tenant_id, user_id=..., role_id=...)`.
- `bind_user_role`
  - Keep tenant check on `User` and `Role`.
  - Update existence check key from `(user_id, role_id)` to `(tenant_id, user_id, role_id)`.
  - Insert link row with explicit `tenant_id`.
- `unbind_user_role`
  - Fetch/delete by composite key `(tenant_id, user_id, role_id)`.
- `collect_user_permissions`
  - Change link query from `where(UserRole.user_id == user_id)` to tenant-scoped:
    - `where(UserRole.tenant_id == tenant_id).where(UserRole.user_id == user_id)`
  - This avoids role leakage when identical IDs exist across tenants.

### Error behavior

- Preserve not-found behavior for cross-tenant bind/unbind.
- Convert unexpected DB integrity violations into controlled `ConflictError` where appropriate.

## Required Test Updates

### Existing test file updates

Target file: `tests/test_identity.py`

- Keep existing tenant isolation and permission tests.
- Add explicit coverage for user-role tenant boundary:
  - cross-tenant `bind_user_role` returns `404`
  - cross-tenant `unbind_user_role` returns `404`
- Add regression for permission collection scoping:
  - a user only receives roles bound in the same `tenant_id`.

### New migration/integration tests

- Add migration-level assertions (new test module) to verify:
  - cross-tenant `user_roles` insert fails at DB level
  - same-tenant `user_roles` insert succeeds
  - composite PK uniqueness enforces no duplicate row per `(tenant_id, user_id, role_id)`

## Rollback Strategy

Rollback should mirror forward migration in reverse order:

1. Drop composite FKs and composite PK on `user_roles`.
2. Restore legacy PK `(user_id, role_id)` and legacy single-column FKs.
3. Keep `user_roles.tenant_id` as nullable during intermediate rollback stage.
4. Drop parent composite unique constraints on `users`/`roles` only after dependent FKs are removed.
5. Optionally drop `user_roles.tenant_id` and new indexes if full rollback to pre-07A identity preview is required.

Data safety notes:

- No destructive data rewrite is required in forward path except backfill.
- Rollback is safe only if existing link rows remain logically consistent with legacy constraints.
- If rollback is executed after tenant-bound links exist, validate integrity before dropping composite constraints.
