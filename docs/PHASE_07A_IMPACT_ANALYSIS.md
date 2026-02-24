# Phase 07A Composite Tenant Constraints - Impact Analysis

## Scope and Inputs

- Scope baseline: `phases/phase-07-tenant-boundary.md:24` (Phase 07A Core Tenant Isolation).
- Current schema/model baseline:
  - `app/domain/models.py`
  - `infra/migrations/versions/202602190002_identity_phase1.py`
  - `infra/migrations/versions/202602190003_registry_phase2.py`
  - `infra/migrations/versions/202602190004_mission_phase3.py`
  - `infra/migrations/versions/202602210007_phase1_to_phase6.py`
- This document is analysis-only and does not include implementation changes.

## Models Affected by 07A Composite Tenant Constraints

### Directly in scope (core 07A models)

| Model | Current state | 07A impact |
|---|---|---|
| `User` | Tenant FK only, no `(tenant_id, id)` unique key (`app/domain/models.py:60`) | Add composite uniqueness as parent for `user_roles` composite FK. |
| `Role` | Tenant FK only, no `(tenant_id, id)` unique key (`app/domain/models.py:72`) | Add composite uniqueness as parent for `user_roles` composite FK. |
| `UserRole` | Only `user_id` + `role_id` PK (`app/domain/models.py:92`) | Add `tenant_id`; change key strategy to tenant-scoped link key; switch to composite FKs to `users` and `roles`. |
| `Drone` | Tenant FK only, no `(tenant_id, id)` unique key (`app/domain/models.py:114`) | Add composite uniqueness as parent for mission/observation tenant-scoped references. |
| `Mission` | `drone_id` single-column FK (`app/domain/models.py:154`) | Replace with composite FK `(tenant_id, drone_id)`; add `(tenant_id, id)` unique key for downstream refs. |
| `MissionRun` | `mission_id` single-column FK (`app/domain/models.py:188`) | Replace with composite FK `(tenant_id, mission_id) -> missions(tenant_id, id)`. |
| `InspectionTemplate` | Tenant FK only (`app/domain/models.py:568`) | Add `(tenant_id, id)` unique key for `inspection_tasks` composite FK. |
| `InspectionTask` | `template_id` and `mission_id` are single-column FKs (`app/domain/models.py:594`) | Replace both with composite FKs; add `(tenant_id, id)` unique key for observations. |
| `InspectionObservation` | `task_id` and `drone_id` are single-column FKs (`app/domain/models.py:608`) | Replace with composite FKs; add `(tenant_id, id)` unique key for defects. |
| `Defect` | `observation_id` single-column FK (`app/domain/models.py:638`) | Replace with composite FK; add `(tenant_id, id)` unique key for defect actions. |
| `DefectAction` | `defect_id` single-column FK (`app/domain/models.py:652`) | Replace with composite FK `(tenant_id, defect_id) -> defects(tenant_id, id)`. |

### Secondary/adjacent models (not explicitly listed as 07A composite targets, but related)

| Model | Why adjacent risk remains |
|---|---|
| `Approval` | Still single FK `mission_id -> missions.id` (`app/domain/models.py:176`), so DB-level cross-tenant insert is still possible unless separately tightened. |
| `InspectionTemplateItem` | Still single FK `template_id -> inspection_templates.id` (`app/domain/models.py:580`). |
| `InspectionExport` | Still single FK `task_id -> inspection_tasks.id` (`app/domain/models.py:627`). |
| `DroneCredential` | Still single FK `drone_id -> drones.id` (`app/domain/models.py:130`). |

## Relationships Requiring Composite FK Update

Phase 07A-required tenant-scoped FK replacements (from `phases/phase-07-tenant-boundary.md:32` and `phases/phase-07-tenant-boundary.md:41`):

| Child table | Current FK | Required 07A FK |
|---|---|---|
| `missions` | `drone_id -> drones.id` (`infra/migrations/versions/202602190004_mission_phase3.py:35`) | `(tenant_id, drone_id) -> drones(tenant_id, id)` (nullable `drone_id`). |
| `mission_runs` | `mission_id -> missions.id` (`infra/migrations/versions/202602190004_mission_phase3.py:72`) | `(tenant_id, mission_id) -> missions(tenant_id, id)`. |
| `inspection_tasks` | `template_id -> inspection_templates.id` (`infra/migrations/versions/202602210007_phase1_to_phase6.py:71`) | `(tenant_id, template_id) -> inspection_templates(tenant_id, id)`. |
| `inspection_tasks` | `mission_id -> missions.id` (`infra/migrations/versions/202602210007_phase1_to_phase6.py:72`) | `(tenant_id, mission_id) -> missions(tenant_id, id)` (nullable `mission_id`). |
| `inspection_observations` | `task_id -> inspection_tasks.id` (`infra/migrations/versions/202602210007_phase1_to_phase6.py:100`) | `(tenant_id, task_id) -> inspection_tasks(tenant_id, id)`. |
| `inspection_observations` | `drone_id -> drones.id` (`infra/migrations/versions/202602210007_phase1_to_phase6.py:101`) | `(tenant_id, drone_id) -> drones(tenant_id, id)` (nullable `drone_id`). |
| `defects` | `observation_id -> inspection_observations.id` (`infra/migrations/versions/202602210007_phase1_to_phase6.py:140`) | `(tenant_id, observation_id) -> inspection_observations(tenant_id, id)`. |
| `defect_actions` | `defect_id -> defects.id` (`infra/migrations/versions/202602210007_phase1_to_phase6.py:158`) | `(tenant_id, defect_id) -> defects(tenant_id, id)`. |
| `user_roles` | `user_id -> users.id` (`infra/migrations/versions/202602190002_identity_phase1.py:80`) | `(tenant_id, user_id) -> users(tenant_id, id)`. |
| `user_roles` | `role_id -> roles.id` (`infra/migrations/versions/202602190002_identity_phase1.py:81`) | `(tenant_id, role_id) -> roles(tenant_id, id)`. |

## Services Impacted

### Primary service impact (requires code path updates)

| Service | Why impacted |
|---|---|
| `IdentityService` | `UserRole` key shape changes will break `session.get(UserRole, (user_id, role_id))` and inserts without `tenant_id` (`app/services/identity_service.py:314`, `app/services/identity_service.py:316`, `app/services/identity_service.py:325`). |
| `MissionService` | `create_mission`/`update_mission` currently accept `drone_id` without explicit in-tenant pre-validation (`app/services/mission_service.py:65`, `app/services/mission_service.py:115`). Composite FK will enforce at DB level and can raise `IntegrityError` on cross-tenant IDs. |
| `InspectionService` | `create_task` and `create_observation` write tenant-owned links that become composite-constrained (`app/services/inspection_service.py:107`, `app/services/inspection_service.py:145`). `mission_id`/`drone_id` need consistent in-tenant checks before insert/update. |
| `DefectService` | Writes through `defects` and `defect_actions` constrained links (`app/services/defect_service.py:56`, `app/services/defect_service.py:147`). Review-task creation path also depends on in-tenant `InspectionTask` lineage (`app/services/defect_service.py:195`). |

### Secondary service impact (indirect or operational)

| Service | Why impacted |
|---|---|
| `IncidentService` | Although incident module is deferred for 07B, it creates `Mission` and `InspectionTask`; caller-provided `template_id` path currently lacks strict tenant validation (`app/services/incident_service.py:62`, `app/services/incident_service.py:76`). Composite FK may surface DB errors if cross-tenant IDs are passed. |
| `RegistryService` | Parent `Drone` rows become referenced by new composite FKs; delete/update behavior should be validated against expected `ON DELETE` effects and error mapping (`app/services/registry_service.py:105`). |
| `ReportingService` | Read-heavy paths over mission/task/defect domains will benefit from composite indexes aligned to tenant+relation predicates (`app/services/reporting_service.py:31`, `app/services/reporting_service.py:55`). |
| `DashboardService` | Tenant-scoped observation/task reads should be checked against updated index strategy (`app/services/dashboard_service.py:44`). |

## Estimated Number of Migrations Required

Recommended estimate: **3 migration revisions** for safe rollout on non-empty databases.

1. Expand schema revision:
   - add `user_roles.tenant_id` as nullable
   - add parent-side composite unique keys `(tenant_id, id)`
   - add child-side composite support indexes
2. Backfill/data validation revision:
   - populate `user_roles.tenant_id`
   - run mismatch checks and fail early on cross-tenant link anomalies
3. Enforce constraints revision:
   - set `user_roles.tenant_id` to `NOT NULL`
   - add composite FKs
   - drop replaced single-column FKs

Minimum possible for greenfield/dev DBs: **2 revisions** (expand+enforce combined, with in-revision backfill), but this increases migration risk on existing data.

## Potential ORM Breakpoints

1. `UserRole` PK/API mismatch:
   - Current `session.get(UserRole, (user_id, role_id))` calls assume 2-column PK and will break after tenant-scoped key change (`app/services/identity_service.py:314`, `app/services/identity_service.py:325`).
2. Insert payload mismatch:
   - `UserRole(...)` currently omits `tenant_id` (`app/services/identity_service.py:316`), which will fail once column is required.
3. Error-mode shift to DB-level `IntegrityError`:
   - Service methods that do not pre-validate linked IDs in-tenant may start failing at commit time:
     - `MissionService` (`app/services/mission_service.py:65`, `app/services/mission_service.py:115`)
     - `InspectionService` (`app/services/inspection_service.py:107`, `app/services/inspection_service.py:145`)
     - `IncidentService` (`app/services/incident_service.py:62`)
4. SQLModel declaration gap for composite FKs:
   - Current models use column-level `Field(foreign_key=...)` patterns; composite FKs require table-level constraints and explicit model metadata updates (`app/domain/models.py`).
5. Parent-key precondition ordering:
   - Composite child FKs depend on parent `(tenant_id, id)` uniqueness existing first; migration ordering mistakes will fail DDL application.

## Performance Index Update Areas

Current migrations mostly create separate single-column indexes (for example `ix_mission_runs_tenant_id` and `ix_mission_runs_mission_id`: `infra/migrations/versions/202602190004_mission_phase3.py:75`, `infra/migrations/versions/202602190004_mission_phase3.py:76`), not tenant+relation composite indexes.

Composite index updates required for 07A workload:

| Table | Required index/constraint update | Why |
|---|---|---|
| `users`, `roles`, `drones`, `missions`, `inspection_templates`, `inspection_tasks`, `inspection_observations`, `defects` | Add unique `(tenant_id, id)` | Parent-side target for composite FKs. |
| `user_roles` | PK/unique `(tenant_id, user_id, role_id)` and secondary `(tenant_id, user_id)` | Fast auth-path role lookup (`app/services/identity_service.py:354`). |
| `missions` | Add `(tenant_id, drone_id)` | Supports composite FK checks and tenant+drone access. |
| `mission_runs` | Add `(tenant_id, mission_id)` | Matches query predicate in run lifecycle updates (`app/services/mission_service.py:250`). |
| `inspection_tasks` | Add `(tenant_id, template_id)` and `(tenant_id, mission_id)` | Required for composite FKs and tenant-scoped relation scans. |
| `inspection_observations` | Add `(tenant_id, task_id)` and `(tenant_id, drone_id)` | Matches list path and relation constraints (`app/services/inspection_service.py:185`). |
| `defects` | Add `(tenant_id, observation_id)` | Matches defect-from-observation lookup (`app/services/defect_service.py:63`). |
| `defect_actions` | Add `(tenant_id, defect_id)` | Matches defect action timeline query (`app/services/defect_service.py:118`). |

Optional but high-value query indexes (post-constraint tuning):

- `inspection_tasks(tenant_id, status)` for task list filtering.
- `defects(tenant_id, status)` and `defects(tenant_id, assigned_to)` for defect boards.
- `inspection_observations(tenant_id, ts)` for latest-observation/dashboard reads.

## Summary

- Direct 07A model impact: **11 models**.
- Required composite FK conversions in 07A scope: **10 relationships**.
- Primary service updates needed: **Identity, Mission, Inspection, Defect**.
- Recommended migration plan: **3 revisions** (2 minimum in low-risk/greenfield scenarios).
