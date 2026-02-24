# PHASE 07A Core Boundary Impact Analysis

## Scope and Baseline

Analysis target is `phases/phase-07a-core-boundary.md` with scope limited to:

- `drones`
- `missions`
- `mission_runs`
- `inspection_templates`
- `inspection_tasks`
- `inspection_observations`
- `defects`
- `defect_actions`

Current implementation baseline:

- Models: `app/domain/models.py`
- Services: `app/services/registry_service.py`, `app/services/mission_service.py`, `app/services/inspection_service.py`, `app/services/defect_service.py`
- Routers: `app/api/routers/registry.py`, `app/api/routers/mission.py`, `app/api/routers/inspection.py`, `app/api/routers/defect.py`
- Current schema history: `infra/migrations/versions/202602190003_registry_phase2.py`, `infra/migrations/versions/202602190004_mission_phase3.py`, `infra/migrations/versions/202602210007_phase1_to_phase6.py`

## 1) SQLAlchemy Model Changes Required

## Tenant Column Requirement

All in-scope tables already have `tenant_id` in model layer and migrations:

- `Drone.tenant_id` (`app/domain/models.py:140`)
- `Mission.tenant_id` (`app/domain/models.py:179`)
- `MissionRun.tenant_id` (`app/domain/models.py:213`)
- `InspectionTemplate.tenant_id` (`app/domain/models.py:593`)
- `InspectionTask.tenant_id` (`app/domain/models.py:619`)
- `InspectionObservation.tenant_id` (`app/domain/models.py:633`)
- `Defect.tenant_id` (`app/domain/models.py:663`)
- `DefectAction.tenant_id` (`app/domain/models.py:677`)

Impact: no new tenant columns expected in model code for these tables; migration Step 2 is primarily validation (and any data repair if historic drift exists).

## Parent Unique `(tenant_id, id)` Requirements

Missing today and required on parent tables:

- `drones` (`Drone` currently only has `uq_drones_tenant_name`: `app/domain/models.py:137`)
- `missions` (`app/domain/models.py:175`)
- `inspection_templates` (`app/domain/models.py:589`)
- `inspection_tasks` (`app/domain/models.py:615`)
- `inspection_observations` (`app/domain/models.py:629`)
- `defects` (`app/domain/models.py:659`)

Model impact:

- Add `__table_args__` `UniqueConstraint("tenant_id", "id", name=...)` for all above parent models.

## Composite FK Declaration Changes

Current scoped child references are single-column `Field(foreign_key=...)`:

- `Mission.drone_id` (`app/domain/models.py:181`)
- `MissionRun.mission_id` (`app/domain/models.py:214`)
- `InspectionTask.template_id` (`app/domain/models.py:621`)
- `InspectionTask.mission_id` (`app/domain/models.py:622`)
- `InspectionObservation.task_id` (`app/domain/models.py:634`)
- `InspectionObservation.drone_id` (`app/domain/models.py:635`)
- `Defect.observation_id` (`app/domain/models.py:664`)
- `DefectAction.defect_id` (`app/domain/models.py:678`)

Model impact:

- Replace the above single-column FK declarations with table-level composite `ForeignKeyConstraint` entries in each child model `__table_args__`.
- Preserve nullable semantics for `Mission.drone_id`, `InspectionTask.mission_id`, `InspectionObservation.drone_id`.

## Indexing Metadata Changes in Models

Current model code mostly uses single-column `index=True`. Core 07A requires composite indexes for tenant-scoped relations and business filters:

- Parent-side `(tenant_id, id)` support
- Child-side `(tenant_id, foreign_id)` for each scoped FK
- Business filters:
  - `missions (tenant_id, state)`
  - `inspection_tasks (tenant_id, status)`
  - `defects (tenant_id, status)`
  - `defects (tenant_id, assigned_to)`
  - `inspection_observations (tenant_id, ts)`

Likely implementation pattern:

- Add `Index(...)` entries in model `__table_args__` where explicit naming/control is needed.

## 2) FK Replacements Needed

Current FK definitions are single-column in migrations:

- `missions.drone_id -> drones.id` (`infra/migrations/versions/202602190004_mission_phase3.py:35`)
- `mission_runs.mission_id -> missions.id` (`infra/migrations/versions/202602190004_mission_phase3.py:72`)
- `inspection_tasks.template_id -> inspection_templates.id` (`infra/migrations/versions/202602210007_phase1_to_phase6.py:71`)
- `inspection_tasks.mission_id -> missions.id` (`infra/migrations/versions/202602210007_phase1_to_phase6.py:72`)
- `inspection_observations.task_id -> inspection_tasks.id` (`infra/migrations/versions/202602210007_phase1_to_phase6.py:100`)
- `inspection_observations.drone_id -> drones.id` (`infra/migrations/versions/202602210007_phase1_to_phase6.py:101`)
- `defects.observation_id -> inspection_observations.id` (`infra/migrations/versions/202602210007_phase1_to_phase6.py:140`)
- `defect_actions.defect_id -> defects.id` (`infra/migrations/versions/202602210007_phase1_to_phase6.py:158`)

Required replacements:

- `missions (tenant_id, drone_id) -> drones (tenant_id, id)` (nullable `drone_id`)
- `mission_runs (tenant_id, mission_id) -> missions (tenant_id, id)`
- `inspection_tasks (tenant_id, template_id) -> inspection_templates (tenant_id, id)`
- `inspection_tasks (tenant_id, mission_id) -> missions (tenant_id, id)` (nullable `mission_id`)
- `inspection_observations (tenant_id, task_id) -> inspection_tasks (tenant_id, id)`
- `inspection_observations (tenant_id, drone_id) -> drones (tenant_id, id)` (nullable `drone_id`)
- `defects (tenant_id, observation_id) -> inspection_observations (tenant_id, id)`
- `defect_actions (tenant_id, defect_id) -> defects (tenant_id, id)`

## 3) Service Method Changes Per Module

## RegistryService (`app/services/registry_service.py`)

Methods requiring change:

- `get_drone` (`app/services/registry_service.py:64`)
- `update_drone` (`app/services/registry_service.py:71`)
- `delete_drone` (`app/services/registry_service.py:103`)

Current pattern:

- `session.get(Drone, drone_id)` then in-Python tenant check.

Required change:

- Use tenant-scoped query path (`select(Drone).where(Drone.tenant_id==...).where(Drone.id==...)`) so lookup itself is tenant-bounded.

## MissionService (`app/services/mission_service.py`)

Methods requiring change:

- `create_mission` (`app/services/mission_service.py:65`)
- `get_mission` (`app/services/mission_service.py:108`)
- `update_mission` (`app/services/mission_service.py:115`)
- `delete_mission` (`app/services/mission_service.py:153`)
- `approve_mission` (`app/services/mission_service.py:163`)
- `list_approvals` (`app/services/mission_service.py:204`)
- `transition_mission` (`app/services/mission_service.py:214`)

Key changes:

- Replace all `session.get(Mission, mission_id)` + tenant check with tenant-scoped query lookups.
- Pre-validate `drone_id` in-tenant on create/update before commit (instead of relying on DB `IntegrityError`).
- Ensure mission-run creation and lookups remain tenant-scoped (already partially scoped in run queries at `app/services/mission_service.py:250`).

## InspectionService (`app/services/inspection_service.py`)

Methods requiring change:

- `get_template` (`app/services/inspection_service.py:64`)
- `create_template_item` (`app/services/inspection_service.py:71`)
- `list_template_items` (`app/services/inspection_service.py:95`)
- `create_task` (`app/services/inspection_service.py:107`)
- `get_task` (`app/services/inspection_service.py:138`)
- `create_observation` (`app/services/inspection_service.py:145`)
- `list_observations` (`app/services/inspection_service.py:179`)
- `create_export` (`app/services/inspection_service.py:191`)

Key changes:

- Remove id-only `session.get` lookups for template/task.
- In `create_task`, validate optional `mission_id` is in tenant (template validation already exists logically, but via id-only fetch).
- In `create_observation`, validate optional `drone_id` is in tenant.
- Keep not-found semantics on cross-tenant references.

## DefectService (`app/services/defect_service.py`)

Methods requiring change:

- `create_from_observation` (`app/services/defect_service.py:56`)
- `get_defect` (`app/services/defect_service.py:111`)
- `assign_defect` (`app/services/defect_service.py:125`)
- `update_status` (`app/services/defect_service.py:147`)
- `_resolve_template_id_for_review` (`app/services/defect_service.py:194`)

Key changes:

- Replace id-only `session.get` for `InspectionObservation`, `Defect`, `InspectionTask` with tenant-scoped query lookups.
- Preserve tenant lineage checks when creating review tasks during `FIXED` transition.

## Secondary impacted modules (cross-module coupling)

- `IncidentService.create_task_for_incident` (`app/services/incident_service.py:62`)
  - writes `Mission` and `InspectionTask`; caller-supplied `template_id` path should enforce tenant-scoped lookup to avoid commit-time composite FK failure.
- `ReportingService.device_utilization` (`app/services/reporting_service.py:53`)
  - currently in-memory id matching; may benefit from explicit tenant-aware joins once composite indexes exist.
- `DashboardService.latest_observations` (`app/services/dashboard_service.py:44`)
  - uses tenant filter already; index shape changes improve read performance.

## 4) Router Endpoints Affected

## Primary API endpoints (directly mapped to scoped tables)

Registry router (`app/api/routers/registry.py`):

- `POST /api/registry/drones`
- `GET /api/registry/drones`
- `GET /api/registry/drones/{drone_id}`
- `PATCH /api/registry/drones/{drone_id}`
- `DELETE /api/registry/drones/{drone_id}`

Mission router (`app/api/routers/mission.py`):

- `POST /api/mission/missions`
- `GET /api/mission/missions`
- `GET /api/mission/missions/{mission_id}`
- `PATCH /api/mission/missions/{mission_id}`
- `DELETE /api/mission/missions/{mission_id}`
- `POST /api/mission/missions/{mission_id}/approve`
- `GET /api/mission/missions/{mission_id}/approvals`
- `POST /api/mission/missions/{mission_id}/transition`

Inspection router (`app/api/routers/inspection.py`):

- `GET /api/inspection/templates`
- `POST /api/inspection/templates`
- `GET /api/inspection/templates/{template_id}`
- `POST /api/inspection/templates/{template_id}/items` (coupled via template ownership check)
- `GET /api/inspection/templates/{template_id}/items` (coupled via template ownership check)
- `POST /api/inspection/tasks`
- `GET /api/inspection/tasks`
- `GET /api/inspection/tasks/{task_id}`
- `POST /api/inspection/tasks/{task_id}/observations`
- `GET /api/inspection/tasks/{task_id}/observations`
- `POST /api/inspection/tasks/{task_id}/export` (coupled via task ownership check)
- `GET /api/inspection/exports/{export_id}` (export out-of-scope table, but ownership checks traverse scoped task lineage)

Defect router (`app/api/routers/defect.py`):

- `POST /api/defects/from-observation/{observation_id}`
- `GET /api/defects`
- `GET /api/defects/stats`
- `GET /api/defects/{defect_id}`
- `POST /api/defects/{defect_id}/assign`
- `POST /api/defects/{defect_id}/status`

## Secondary endpoints affected by scoped-table writes/reads

Incident router (`app/api/routers/incident.py`):

- `POST /api/incidents/{incident_id}/create-task` (creates `missions` + `inspection_tasks`)

UI router (`app/api/routers/ui.py`):

- `GET /ui/inspection`
- `GET /ui/inspection/tasks/{task_id}`
- `GET /ui/defects`

Dashboard/reporting endpoints are not direct write surfaces, but query plans/latency are affected by index strategy:

- `GET /api/dashboard/stats`
- `GET /api/dashboard/observations`
- `GET /api/reporting/overview`
- `GET /api/reporting/closure-rate`
- `GET /api/reporting/device-utilization`
- `POST /api/reporting/export`

## 5) ORM Areas Likely Needing Explicit Join Definitions

Current code uses SQLModel without `Relationship(...)` links for these entities. If relationships are introduced (or eager-loading is added), composite keys will likely require explicit join config to avoid ambiguous inference.

Highest-likelihood areas:

- `Mission` <-> `Drone` via `(tenant_id, drone_id)` and `(tenant_id, id)`
- `MissionRun` <-> `Mission` via `(tenant_id, mission_id)`
- `InspectionTask` <-> `InspectionTemplate` via `(tenant_id, template_id)`
- `InspectionTask` <-> `Mission` via `(tenant_id, mission_id)` (same child also has template relation; shared `tenant_id` increases ambiguity risk)
- `InspectionObservation` <-> `InspectionTask` and `Drone` (two composite refs sharing `tenant_id`)
- `Defect` <-> `InspectionObservation`
- `DefectAction` <-> `Defect`

Likely explicit config needs (if relationships are added):

- explicit `foreign_keys` list
- explicit `primaryjoin` including both `tenant_id` and id columns
- explicit `back_populates` naming to avoid accidental overlapping relationship warnings

## 6) Estimated Number of Migration Revisions

Estimated revisions for core scope: **3** (aligned to mandatory 3-step model).

- Revision A: Expand
  - add parent `(tenant_id, id)` unique constraints
  - add composite indexes
  - keep legacy single-column FKs
- Revision B: Backfill + Validate
  - validate tenant consistency for all scoped child-parent links
  - fail fast with mismatch details
- Revision C: Enforce
  - add composite FKs
  - drop replaced single-column FKs
  - finalize `NOT NULL` posture (already present on scoped tables in current schema, but include assertion/guard)

Optional operational split: 4 revisions if enforcement is divided by domain (`mission*` vs `inspection/defect*`) to reduce lock duration and rollback blast radius.

## 7) Risk Hotspots in Enforcement Step

1. Existing data mismatches across tenant-linked ids
   - Composite FK add will fail immediately if historical cross-tenant rows exist.
2. Constraint ordering dependency
   - Parent `UNIQUE (tenant_id, id)` must exist before child composite FK creation.
3. Locking/DDL pressure on high-write tables
   - `missions`, `inspection_tasks`, `inspection_observations`, `defects`, `defect_actions` are active write paths.
4. Nullable FK edge handling
   - `drone_id` and `mission_id` nullable references must preserve intended `ON DELETE` behavior under composite constraints.
5. Service error-mode shift
   - If pre-validation is incomplete, failures move from controlled `404`/`409` to raw commit-time `IntegrityError`.
6. Id-only lookup remnants
   - Remaining `session.get(..., id)` patterns can produce inconsistent boundary behavior and make auditing harder.
7. Out-of-scope dependent tables remain single-FK
   - `approvals`, `inspection_template_items`, `inspection_exports`, `drone_credentials` keep single-column refs; not a blocker for this phase, but creates mixed-consistency surface.
8. SQLite vs PostgreSQL behavior differences in tests
   - FK enforcement in SQLite requires explicit `PRAGMA foreign_keys=ON`; missing this can hide violations.
9. Incident flow coupling
   - `POST /api/incidents/{incident_id}/create-task` can hit composite FK failures if template ownership validation remains weak.
10. Downgrade complexity
    - Must drop composite FKs before parent unique constraints; incorrect order causes downgrade failure.

## Summary

- Core 07A model work is substantial but bounded: scoped models need composite uniqueness/FK/index metadata updates, not tenant-column additions.
- Primary behavioral change is service-layer lookup hardening: eliminate id-only entity access patterns.
- API contract can remain stable (`404` on cross-tenant access), but implementation must shift to tenant-scoped query paths before enforcement.
- A strict 3-revision migration sequence is feasible; enforcement risk is dominated by pre-existing data quality and incomplete pre-validation paths.
