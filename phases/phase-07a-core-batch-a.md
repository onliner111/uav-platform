# Phase 07A Core Batch A - Tenant Composite Boundary Spec

## Scope (Only)

This batch is strictly limited to:

- `drones`
- `missions`
- `mission_runs`

Out of scope:

- Any table outside the list above
- Inspection and defect domains
- Identity domain
- Peripheral modules (`incidents`, `alerts`, `command_requests`)

## Objectives

1. Enforce DB-level tenant-safe references between `missions`/`mission_runs` and their parents.
2. Eliminate id-only access patterns in service paths for scoped entities.
3. Preserve API behavior for in-tenant flows while returning not-found style behavior for cross-tenant access.

## Required Composite UNIQUE Constraints

Add parent-side composite uniqueness to support composite FKs:

- `drones`: `UNIQUE (tenant_id, id)`
- `missions`: `UNIQUE (tenant_id, id)`

Notes:

- Existing `UNIQUE (tenant_id, name)` on `drones` remains unchanged.
- `mission_runs` is a child in this batch and does not require parent-target composite uniqueness for this scope.

## Required Composite FKs

Replace single-column tenant-unsafe references with tenant-scoped composite FKs:

- `missions (tenant_id, drone_id) -> drones (tenant_id, id)` (`drone_id` nullable)
- `mission_runs (tenant_id, mission_id) -> missions (tenant_id, id)`

Drop replaced legacy FKs during enforcement:

- `missions.drone_id -> drones.id`
- `mission_runs.mission_id -> missions.id`

## Required Indexes

Add/update indexes for constraint checks and query performance:

- Parent support:
  - `drones (tenant_id, id)` (unique)
  - `missions (tenant_id, id)` (unique)
- Child relation indexes:
  - `missions (tenant_id, drone_id)`
  - `mission_runs (tenant_id, mission_id)`
- Business/filter indexes:
  - `missions (tenant_id, state)`
  - optional tuning: `missions (tenant_id, created_at)` if timeline-heavy reads are common

## Service-Layer Lookup Hardening

## RegistryService

Target: `app/services/registry_service.py`

Required changes:

- Replace id-only lookup patterns (`session.get(Drone, drone_id)`) with tenant-scoped query lookup in:
  - `get_drone`
  - `update_drone`
  - `delete_drone`

Rule:

- No scoped entity read/write by id alone.
- Lookup must include tenant predicate in the same query path.

## MissionService

Target: `app/services/mission_service.py`

Required changes:

- Replace id-only mission lookups (`session.get(Mission, mission_id)`) with tenant-scoped query lookup in:
  - `get_mission`
  - `update_mission`
  - `delete_mission`
  - `approve_mission`
  - `list_approvals` (mission existence check)
  - `transition_mission`
- Add explicit in-tenant validation for `drone_id` on:
  - `create_mission`
  - `update_mission`

Behavior requirement:

- Cross-tenant references and id access return `404` semantics (not resource-disclosing errors).

## Migration Plan (Mandatory 3-Step Model)

## Step 1: Expand

- Add `UNIQUE (tenant_id, id)` on `drones` and `missions`.
- Add composite indexes:
  - `(tenant_id, drone_id)` on `missions`
  - `(tenant_id, mission_id)` on `mission_runs`
  - `(tenant_id, state)` on `missions`
- Keep legacy single-column FKs in place during this step.

## Step 2: Backfill + Validate

- Validate data consistency for future composite relations:
  - `missions.drone_id` (when non-null) points to drone with same tenant
  - `mission_runs.mission_id` points to mission with same tenant
- Fail migration if any mismatch exists, with actionable mismatch output.
- No enforce-step execution unless validation is clean.

## Step 3: Enforce

- Add composite FK constraints:
  - `(tenant_id, drone_id) -> drones(tenant_id, id)`
  - `(tenant_id, mission_id) -> missions(tenant_id, id)`
- Drop legacy single-column FKs replaced above.
- Preserve nullable behavior for `missions.drone_id`.
- Keep downgrade path explicit and in reverse-safe order.

## Test Updates

## API/Service Tests

Add/extend tests for:

- cross-tenant drone id access returns `404`
  - registry get/update/delete by id
- cross-tenant mission id access returns `404`
  - mission get/update/delete/approve/transition/list-approvals
- mission create/update rejects cross-tenant `drone_id` with not-found style behavior

## DB-Level Constraint Tests

Add migration/integration tests validating:

- cross-tenant insert/update fails for:
  - `missions (tenant_id, drone_id)`
  - `mission_runs (tenant_id, mission_id)`
- same-tenant insert/update succeeds

SQLite testing requirement:

- Enable FK enforcement in test setup: `PRAGMA foreign_keys=ON`.

## Verification Checklist

Before marking Batch A complete:

- `ruff` passes
- `mypy` passes
- `pytest` passes
- `e2e` passes
- `alembic upgrade head` passes on clean DB
- Schema inspection confirms:
  - required composite unique constraints
  - required composite FKs
  - required composite indexes
- Negative verification confirms cross-tenant DB writes fail.
- API verification confirms cross-tenant id access returns `404`.

## Non-Implementation Note

- This file is specification-only.
- No code or migration implementation is performed by this document.
