# Phase 07A/07B — Tenant Boundary Enforcement

## Phase split

- `Phase 07A - Core Tenant Isolation` is the immediate delivery scope.
- `Phase 07B - Peripheral Modules` is explicitly deferred from 07A.
- This split refines specification scope only; migration model remains unchanged.

## Objectives

### Phase 07A - Core Tenant Isolation

- Enforce hard tenant isolation for core operational entities, not only at API filtering level.
- Prevent cross-tenant references in core workflows from being inserted, updated, or queried.
- Standardize tenant-scoped read/write patterns for core services so boundary checks are consistent and auditable.
- Add regression coverage to ensure future core features cannot bypass tenant boundary rules.

### Phase 07B - Peripheral Modules

- Extend the same boundary guarantees to deferred peripheral modules after 07A stabilizes.

## Required DB changes

### Phase 07A - Core Tenant Isolation

- Limit 07A entity scope to:
  - `users`, `roles`, `user_roles`
  - `drones`, `missions`, `mission_runs`
  - `inspection_templates`, `inspection_tasks`, `inspection_observations`
  - `defects`, `defect_actions`
- Add composite uniqueness `(tenant_id, id)` on 07A tenant-owned parent tables referenced by other 07A tenant-owned tables.
- Replace single-column foreign keys with tenant-scoped composite foreign keys where relationship must remain in-tenant:
  - `missions (tenant_id, drone_id) -> drones (tenant_id, id)` (nullable `drone_id`)
  - `mission_runs (tenant_id, mission_id) -> missions (tenant_id, id)`
  - `inspection_tasks (tenant_id, template_id) -> inspection_templates (tenant_id, id)`
  - `inspection_tasks (tenant_id, mission_id) -> missions (tenant_id, id)` (nullable `mission_id`)
  - `inspection_observations (tenant_id, task_id) -> inspection_tasks (tenant_id, id)`
  - `inspection_observations (tenant_id, drone_id) -> drones (tenant_id, id)` (nullable `drone_id`)
  - `defects (tenant_id, observation_id) -> inspection_observations (tenant_id, id)`
  - `defect_actions (tenant_id, defect_id) -> defects (tenant_id, id)`
- Add `tenant_id` to `user_roles` and enforce:
  - `(tenant_id, user_id) -> users (tenant_id, id)`
  - `(tenant_id, role_id) -> roles (tenant_id, id)`
  - primary key or unique key on `(tenant_id, user_id, role_id)`
- Add or update composite indexes to support new constraints and common query predicates:
  - at minimum `(tenant_id, <foreign_key_column>)` on all 07A child tables listed above.
- Keep global/shared tables unchanged where tenant ownership is intentionally global:
  - `tenants`, `permissions`, `role_permissions` (unless Phase 07 explicitly chooses tenant-copy permissions later).

### Phase 07B - Peripheral Modules

- Defer tenant-boundary DB enforcement for:
  - `incidents`
  - `alerts`
  - `command_requests`
- Apply the same composite uniqueness/FK/index pattern from 07A to deferred modules in 07B.

## Required model updates

### Phase 07A - Core Tenant Isolation

- Introduce a common tenant-owned model convention (mixin or explicit pattern) for 07A models:
  - `tenant_id` required and indexed
  - consistent FK declarations for tenant-scoped references
- Update SQLModel table metadata to reflect composite constraints/keys introduced in migration for 07A models:
  - composite `UniqueConstraint` definitions for parent tables
  - composite `ForeignKeyConstraint` definitions for tenant-scoped relations
- Update association models:
  - `UserRole` must include `tenant_id` and composite keys
- Ensure read/write DTOs never accept client-supplied `tenant_id` for tenant-owned resources:
  - tenant context always derived from auth claims/service boundary.

### Phase 07B - Peripheral Modules

- Extend the same model conventions to `incidents`, `alerts`, and `command_requests`.

## Required service layer enforcement

### Phase 07A - Core Tenant Isolation

- Create a shared tenant-scoped lookup pattern used by all core services:
  - lookup by id must include tenant match in the same query path
  - failed boundary check returns not-found style error (`404` semantics) to avoid resource enumeration
- Enforce tenant boundary before write operations that reference other entities:
  - `MissionService`: validate `drone_id` belongs to tenant on create/update
  - `InspectionService`: validate `mission_id`, `template_id`, `drone_id`, `task_id` within tenant
  - `DefectService`: validate observation/task lineage remains in tenant
  - `IdentityService`: when binding user-role, persist/validate `tenant_id` on link rows
- Add a single boundary utility/helper to reduce copy-paste checks and inconsistent behavior.

### Phase 07B - Peripheral Modules

- Add deferred service boundary enforcement for:
  - `IncidentService` tenant checks
  - command request in-tenant drone ownership checks
  - alert tenant correctness handling

## Required tests

### Phase 07A - Core Tenant Isolation

- DB constraint tests (migration/integration level):
  - verify cross-tenant FK inserts fail for every 07A tenant-scoped relation listed above
  - verify valid same-tenant inserts succeed
  - verify `user_roles` cannot bind user and role from different tenants
- Service tests:
  - mission create/update rejects cross-tenant `drone_id`
  - inspection task creation rejects cross-tenant `template_id` and `mission_id`
  - observation creation rejects cross-tenant `task_id`/`drone_id`
  - defect creation/status workflows reject cross-tenant references
  - identity user-role bind/unbind enforces tenant boundary with new link schema
- API regression tests:
  - cross-tenant id access returns `404` (not `403`) for protected resource endpoints
  - existing in-tenant core workflows remain green
- Backward compatibility tests:
  - existing phase 1-6 demos/tests run unchanged under Phase 07 constraints.

### Phase 07B - Peripheral Modules

- Add deferred tests for:
  - incident cross-tenant reference rejection
  - command request cross-tenant drone rejection
  - alert tenant-bounded creation/update behavior

## Migration strategy

- Step 1: Pre-check and data audit script
  - detect existing cross-tenant mismatches in relational links
  - block migration if unsafe rows exist, with clear remediation output
- Step 2: Expand schema (non-breaking)
  - add missing columns (for example `user_roles.tenant_id`) nullable initially
  - add new indexes needed for composite lookups
- Step 3: Backfill
  - populate new `tenant_id` fields from trusted parent rows
  - re-check for mismatches; fail if unresolved
- Step 4: Enforce constraints
  - add composite unique constraints and composite foreign keys
  - switch new columns to `NOT NULL`
  - drop obsolete single-column FKs that do not enforce tenant scope
- Step 5: Application rollout
  - deploy service-layer enforcement with migration
  - run full test and demo suite immediately after migration
- Step 6: Downgrade plan
  - provide explicit downgrade steps for newly added constraints/columns
  - document any non-reversible data assumptions.

## Verification steps

### Phase 07A - Core Tenant Isolation

- Schema verification:
  - inspect generated DB schema for all composite unique/FK constraints
  - confirm expected indexes exist for new composite predicates
- Negative verification:
  - attempt direct DB insert/update with cross-tenant references; verify DB rejection
  - attempt API/service operations with cross-tenant IDs; verify not-found behavior
- Positive verification:
  - execute normal same-tenant flows for identity, registry, mission, inspection, defect
- End-to-end verification:
  - run existing demo scripts for phases 1-6 and ensure no regression
  - run smoke verification script after migration on clean environment.

### Phase 07B - Peripheral Modules

- Extend verification to incident, command, and alert workflows after 07A is complete.

## Quality gate checklist

- `docker compose -f infra/docker-compose.yml run --rm --build app ruff check app tests infra/scripts` passes.
- `docker compose -f infra/docker-compose.yml run --rm --build app mypy app` passes.
- `docker compose -f infra/docker-compose.yml run --rm --build app pytest -q` passes, including new tenant-boundary tests.
- Docker Compose e2e chain passes with no phase 1-6 regression (`up --build -d` + `alembic upgrade head` + OpenAPI export + `demo_e2e.py` + `verify_smoke.py`).
- Alembic upgrade and downgrade succeed for Phase 07 revision in a clean DB.
- No cross-tenant write path remains in service code for 07A tenant-owned entities.
- Cross-tenant API access consistently returns not-found semantics for 07A scope.
- Phase output includes:
  - delivered boundary controls
  - verification evidence
  - known risks/follow-ups (including deferred 07B modules).
