# Phase 07A Core Boundary - Composite Tenant Enforcement Spec

## Scope (Only)

This sub-phase applies only to:

- `drones`
- `missions`
- `mission_runs`
- `inspection_templates`
- `inspection_tasks`
- `inspection_observations`
- `defects`
- `defect_actions` (table exists; included in scope)

Out of scope:

- identity tables (`users`, `roles`, `user_roles`, `permissions`, `role_permissions`)
- peripheral modules (`incidents`, `alerts`, `command_requests`, `approval_records`, `inspection_template_items`, `inspection_exports`, `approvals`, `drone_credentials`)
- any non-listed table

## Objectives

1. Enforce hard tenant boundaries in schema and service paths for the scoped core tables.
2. Prevent cross-tenant references at DB level using composite FK constraints.
3. Standardize tenant-scoped lookup/write behavior so no scoped resource is accessed by id alone.
4. Preserve existing API behavior semantics for valid in-tenant workflows.

## Data Model Requirements

### 1) Tenant Column Requirement

- Ensure `tenant_id` exists on every in-scope table.
- Ensure `tenant_id` is `NOT NULL` after backfill/validation.

Tables in scope requiring explicit verification:

- `drones.tenant_id`
- `missions.tenant_id`
- `mission_runs.tenant_id`
- `inspection_templates.tenant_id`
- `inspection_tasks.tenant_id`
- `inspection_observations.tenant_id`
- `defects.tenant_id`
- `defect_actions.tenant_id`

### 2) Parent Uniqueness Requirement

Add `UNIQUE (tenant_id, id)` on parent tables that are referenced by composite FKs in this scope:

- `drones`
- `missions`
- `inspection_templates`
- `inspection_tasks`
- `inspection_observations`
- `defects`

### 3) Composite FK Conversion Requirement

Replace single-column relationships with tenant-scoped composite FKs:

- `missions (tenant_id, drone_id) -> drones (tenant_id, id)` (`drone_id` nullable)
- `mission_runs (tenant_id, mission_id) -> missions (tenant_id, id)`
- `inspection_tasks (tenant_id, template_id) -> inspection_templates (tenant_id, id)`
- `inspection_tasks (tenant_id, mission_id) -> missions (tenant_id, id)` (`mission_id` nullable)
- `inspection_observations (tenant_id, task_id) -> inspection_tasks (tenant_id, id)`
- `inspection_observations (tenant_id, drone_id) -> drones (tenant_id, id)` (`drone_id` nullable)
- `defects (tenant_id, observation_id) -> inspection_observations (tenant_id, id)`
- `defect_actions (tenant_id, defect_id) -> defects (tenant_id, id)`

## Indexing Requirements

### 4) Composite Index Requirement

Add/ensure indexes to support tenant-scoped constraints and query paths:

- Parent-side:
  - `(tenant_id, id)` on all parent tables listed in this scope.
- Child-side composite relation indexes:
  - `missions (tenant_id, drone_id)`
  - `mission_runs (tenant_id, mission_id)`
  - `inspection_tasks (tenant_id, template_id)`
  - `inspection_tasks (tenant_id, mission_id)`
  - `inspection_observations (tenant_id, task_id)`
  - `inspection_observations (tenant_id, drone_id)`
  - `defects (tenant_id, observation_id)`
  - `defect_actions (tenant_id, defect_id)`

### Business/Filtering Indexes

Add tenant-prefixed business indexes where relevant:

- `missions (tenant_id, state)`
- `inspection_tasks (tenant_id, status)`
- `defects (tenant_id, status)`
- `defects (tenant_id, assigned_to)` (if assigned workflow remains in use)
- `inspection_observations (tenant_id, ts)` for recency queries

## Service Layer Enforcement

### 5) Universal Tenant Filter Rule

For scoped modules/services, enforce:

- No read/write path may resolve scoped entities by `id` alone.
- Every lookup for scoped entities must include tenant predicate in the same query path.
- Cross-tenant attempts must return not-found semantics (`404`) to avoid enumeration.

Service modules in-scope for this rule:

- `RegistryService` (`drones`)
- `MissionService` (`missions`, `mission_runs`)
- `InspectionService` (`inspection_templates`, `inspection_tasks`, `inspection_observations`)
- `DefectService` (`defects`, `defect_actions`)

### Required Validation Before Writes

- `MissionService`: validate `drone_id` belongs to tenant for create/update.
- `InspectionService`:
  - task create validates `template_id` and optional `mission_id` in-tenant
  - observation create validates `task_id` and optional `drone_id` in-tenant
- `DefectService`:
  - defect create validates `observation_id` in-tenant
  - defect action/status paths validate `defect_id` in-tenant

## Migration Strategy (Mandatory 3-Step Model)

### 6) Expand

- Add any missing `tenant_id` columns as nullable in scoped tables.
- Add required parent unique constraints `(tenant_id, id)`.
- Add composite indexes needed for upcoming FK checks and tenant-scoped queries.
- Keep legacy single-column FKs temporarily during this step.

### 7) Backfill + Validate (Fail if mismatch)

- Backfill new `tenant_id` fields from trusted parent links.
- Validate every soon-to-be composite relation:
  - child `tenant_id` matches referenced parent `tenant_id`
  - nullable FK columns are validated only when non-null
- Abort migration with explicit mismatch details if any violation exists.
- Block transition to enforce step unless data is clean.

### 8) Enforce

- Set all scoped `tenant_id` columns to `NOT NULL`.
- Create composite FKs for all listed relationships.
- Drop obsolete single-column FKs replaced by composite constraints.
- Keep downgrade path explicit and ordered (drop composite FKs before parent unique constraints).

## Testing Requirements

### 7) API/Service Isolation Tests

Add/extend tests so cross-tenant access to scoped resources is blocked with `404`:

- drones by id (read/update/delete)
- missions by id (read/update/delete/state/approval flows where applicable)
- inspection templates/tasks/observations by id
- defects/defect actions by id

Ensure in-tenant operations remain green.

### DB-Level Constraint Tests

Add migration/integration tests validating DB rejects cross-tenant references:

- each composite FK listed in this spec has:
  - one negative insert/update case (must fail)
  - one positive same-tenant case (must pass)

SQLite-based tests must enable FK enforcement:

- execute `PRAGMA foreign_keys=ON` in test DB setup.

## Verification Checklist

### 8) Required Verification Before Completion

- `ruff` passes
- `mypy` passes
- `pytest` passes
- `e2e` passes
- `alembic upgrade head` passes on clean database

Additional verification:

- schema inspection confirms all required unique/composite FK/index artifacts
- cross-tenant negative cases fail at DB level
- cross-tenant API access returns `404` for in-scope resources

## Non-Implementation Note

### 9) This Document Is Spec-Only

- This phase document defines required behavior and delivery constraints.
- No implementation is performed by this spec itself.
