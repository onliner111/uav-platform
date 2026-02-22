# SYSTEM SNAPSHOT

Generated from repository scan on 2026-02-22.

## 1. Project Structure Tree (max depth 4)
```text
.github/
  workflows/
    ci.yml
app/
  adapters/
    __init__.py
    base.py
    dji_adapter.py
    fake_adapter.py
    mavlink_adapter.py
  api/
    routers/
      __init__.py
      alert.py
      approval.py
      command.py
      dashboard.py
      defect.py
      identity.py
      incident.py
      inspection.py
      mission.py
      registry.py
      reporting.py
      telemetry.py
      ui.py
    __init__.py
    deps.py
  domain/
    __init__.py
    models.py
    permissions.py
    state_machine.py
  infra/
    __init__.py
    audit.py
    auth.py
    db.py
    events.py
    migrate.py
    openapi_export.py
    redis_state.py
    tenant.py
  services/
    __init__.py
    alert_service.py
    command_service.py
    compliance_service.py
    dashboard_service.py
    defect_service.py
    identity_service.py
    incident_service.py
    inspection_service.py
    mission_service.py
    registry_service.py
    reporting_service.py
    telemetry_service.py
  web/
    static/
      command_center.js
      defects.js
      emergency.js
      inspection_task.js
      ui.css
    templates/
      command_center.html
      defects.html
      emergency.html
      inspection_list.html
      inspection_task_detail.html
  __init__.py
  main.py
doc/
  Admin_Manual_V1.0.md
  Admin_Manual_V2.0.md
  API_Appendix_V2.0.md
  Architecture_Overview_V1.0.md
  Architecture_Overview_V2.0.md
  Deployment_Guide_V1.0.md
  Deployment_Guide_V2.0.md
  User_Manual_V1.0.md
  User_Manual_V2.0.md
tooling/gpt/
  gen_report1.sh
  gen_report2.sh
infra/
  migrations/
    versions/
      202602190001_init_phase0.py
      202602190002_identity_phase1.py
      202602190003_registry_phase2.py
      202602190004_mission_phase3.py
      202602190005_command_phase5.py
      202602190006_alert_phase7.py
      202602210007_phase1_to_phase6.py
    env.py
    script.py.mako
  scripts/
    demo_command_center_phase4.py
    demo_common.py
    demo_compliance_phase5.py
    demo_defect_phase2.py
    demo_e2e.py
    demo_emergency_phase3.py
    demo_inspection_phase1.py
    demo_reporting_phase6.py
    run_all_phases.sh
    verify_all.sh
    verify_openapi_client.py
    verify_smoke.py
  docker-compose.yml
logs/
  phase-01-inspection.md.report.md
  phase-02-defect-closure.md.report.md
  phase-03-emergency.md.report.md
  phase-04-command-center.md.report.md
  phase-05-compliance.md.report.md
  phase-06-reporting.md.report.md
  PROGRESS.md
  README.md
openapi/
  clients/
    .gitkeep
phases/
  index.md
  phase-01-inspection.md
  phase-02-defect-closure.md
  phase-03-emergency.md
  phase-04-command-center.md
  phase-05-compliance.md
  phase-06-reporting.md
  reporting.md
  resume.md
  state.md
tests/
  test_adapters.py
  test_alert.py
  test_command.py
  test_events.py
  test_health.py
  test_identity.py
  test_mission.py
  test_registry.py
  test_telemetry.py
.env.example
.gitignore
[app
[internal]
11.10.1
governance/AGENTS.md
alembic.ini
governance/EXECUTION_PLAYBOOK.md
docker-compose.yml
Dockerfile
Makefile
pyproject.toml
requirements-dev.txt
requirements.txt
governance/ROADMAP.md
```

## 2. Main Modules and Responsibilities
- `app/main.py`: FastAPI application bootstrap; router registration; middleware; static mount; health/ready probes.
- `app/api/routers/*`: HTTP/WebSocket API layer for identity, registry, mission, telemetry, command, alerts, inspection, defects, incidents, dashboard, approvals, reporting, and demo UI.
- `app/api/deps.py`: Auth token decode and permission enforcement dependencies.
- `app/services/*`: Business logic per domain:
  - `identity_service.py`: tenant/user/role/permission and RBAC bindings + dev login.
  - `registry_service.py`: drone CRUD.
  - `mission_service.py`: mission lifecycle, approvals, and state transitions.
  - `telemetry_service.py`: telemetry ingest/latest-state read.
  - `command_service.py`: command dispatch, adapter ACK/timeout/failure handling.
  - `alert_service.py`: telemetry rule evaluation and alert lifecycle.
  - `inspection_service.py`: templates, tasks, observations, exports.
  - `defect_service.py`: defect creation/assignment/state transitions/stats.
  - `incident_service.py`: incident CRUD and emergency task creation.
  - `dashboard_service.py`: dashboard stats and recent observations.
  - `compliance_service.py`: approval records and audit export.
  - `reporting_service.py`: reporting KPIs/utilization/report export.
- `app/domain/models.py`: SQLModel tables + Pydantic schemas + enums.
- `app/domain/state_machine.py`: allowed mission state transitions.
- `app/domain/permissions.py`: permission constants and checks.
- `app/adapters/*`: adapter protocol + fake/DJI/MAVLink implementations.
- `app/infra/*`: DB engine/session, audit middleware, JWT auth, event bus, Redis state client, migration/openapi helpers.
- `infra/migrations/*`: Alembic migrations.
- `infra/scripts/*`: demo/verification scripts for phases and smoke/E2E.
- `tests/*`: API/service behavior tests.

## 3. Database Models (Tables + Fields)
From `app/domain/models.py` table definitions:

- `events`: `event_id`, `event_type`, `tenant_id`, `ts`, `actor_id`, `correlation_id`, `payload`
- `audit_logs`: `id`, `tenant_id`, `actor_id`, `action`, `resource`, `method`, `status_code`, `ts`, `detail`
- `tenants`: `id`, `name`, `created_at`
- `users`: `id`, `tenant_id`, `username`, `password_hash`, `is_active`, `created_at`
- `roles`: `id`, `tenant_id`, `name`, `description`, `created_at`
- `permissions`: `id`, `name`, `description`, `created_at`
- `user_roles`: `user_id`, `role_id`, `created_at`
- `role_permissions`: `role_id`, `permission_id`, `created_at`
- `drones`: `id`, `tenant_id`, `name`, `vendor`, `capabilities`, `created_at`, `updated_at`
- `drone_credentials`: `id`, `tenant_id`, `drone_id`, `secret`, `created_at`
- `missions`: `id`, `tenant_id`, `name`, `drone_id`, `plan_type`, `payload`, `constraints`, `state`, `created_by`, `created_at`, `updated_at`
- `approvals`: `id`, `tenant_id`, `mission_id`, `approver_id`, `decision`, `comment`, `created_at`
- `mission_runs`: `id`, `tenant_id`, `mission_id`, `state`, `started_at`, `ended_at`
- `command_requests`: `id`, `tenant_id`, `drone_id`, `command_type`, `params`, `idempotency_key`, `expect_ack`, `status`, `ack_ok`, `ack_message`, `attempts`, `issued_by`, `issued_at`, `updated_at`
- `alerts`: `id`, `tenant_id`, `drone_id`, `alert_type`, `severity`, `status`, `message`, `detail`, `first_seen_at`, `last_seen_at`, `acked_by`, `acked_at`, `closed_by`, `closed_at`
- `inspection_templates`: `id`, `tenant_id`, `name`, `category`, `description`, `is_active`, `created_at`
- `inspection_template_items`: `id`, `tenant_id`, `template_id`, `code`, `title`, `severity_default`, `required`, `sort_order`, `created_at`
- `inspection_tasks`: `id`, `tenant_id`, `name`, `template_id`, `mission_id`, `area_geom`, `priority`, `status`, `created_at`
- `inspection_observations`: `id`, `tenant_id`, `task_id`, `drone_id`, `ts`, `position_lat`, `position_lon`, `alt_m`, `item_code`, `severity`, `note`, `media_url`, `confidence`, `created_at`
- `inspection_exports`: `id`, `tenant_id`, `task_id`, `format`, `file_path`, `created_at`
- `defects`: `id`, `tenant_id`, `observation_id`, `title`, `description`, `severity`, `status`, `assigned_to`, `created_at`
- `defect_actions`: `id`, `tenant_id`, `defect_id`, `action_type`, `note`, `created_at`
- `incidents`: `id`, `tenant_id`, `title`, `level`, `location_geom`, `status`, `linked_task_id`, `created_at`
- `approval_records`: `id`, `tenant_id`, `entity_type`, `entity_id`, `status`, `approved_by`, `created_at`

## 4. API Endpoints Summary
Registered route decorators: 86.

### System
- `GET /healthz`
- `GET /readyz`

### Identity (`/api/identity`)
- `POST /tenants`
- `GET /tenants`
- `GET /tenants/{tenant_id}`
- `PATCH /tenants/{tenant_id}`
- `DELETE /tenants/{tenant_id}`
- `POST /bootstrap-admin`
- `POST /dev-login`
- `POST /users`
- `GET /users`
- `GET /users/{user_id}`
- `PATCH /users/{user_id}`
- `DELETE /users/{user_id}`
- `POST /roles`
- `GET /roles`
- `GET /roles/{role_id}`
- `PATCH /roles/{role_id}`
- `DELETE /roles/{role_id}`
- `POST /permissions`
- `GET /permissions`
- `GET /permissions/{permission_id}`
- `PATCH /permissions/{permission_id}`
- `DELETE /permissions/{permission_id}`
- `POST /users/{user_id}/roles/{role_id}`
- `DELETE /users/{user_id}/roles/{role_id}`
- `POST /roles/{role_id}/permissions/{permission_id}`
- `DELETE /roles/{role_id}/permissions/{permission_id}`

### Registry (`/api/registry`)
- `POST /drones`
- `GET /drones`
- `GET /drones/{drone_id}`
- `PATCH /drones/{drone_id}`
- `DELETE /drones/{drone_id}`

### Mission (`/api/mission`)
- `POST /missions`
- `GET /missions`
- `GET /missions/{mission_id}`
- `PATCH /missions/{mission_id}`
- `DELETE /missions/{mission_id}`
- `POST /missions/{mission_id}/approve`
- `GET /missions/{mission_id}/approvals`
- `POST /missions/{mission_id}/transition`

### Telemetry (`/api/telemetry` + WS)
- `POST /ingest`
- `GET /drones/{drone_id}/latest`
- `WEBSOCKET /ws/drones`

### Command (`/api/command`)
- `POST /commands`
- `GET /commands`
- `GET /commands/{command_id}`

### Alert (`/api/alert`)
- `GET /alerts`
- `GET /alerts/{alert_id}`
- `POST /alerts/{alert_id}/ack`
- `POST /alerts/{alert_id}/close`

### Inspection (`/api/inspection`)
- `GET /templates`
- `POST /templates`
- `GET /templates/{template_id}`
- `POST /templates/{template_id}/items`
- `GET /templates/{template_id}/items`
- `POST /tasks`
- `GET /tasks`
- `GET /tasks/{task_id}`
- `POST /tasks/{task_id}/observations`
- `GET /tasks/{task_id}/observations`
- `POST /tasks/{task_id}/export`
- `GET /exports/{export_id}`

### Defects (`/api/defects`)
- `POST /from-observation/{observation_id}`
- `GET /`
- `GET /stats`
- `GET /{defect_id}`
- `POST /{defect_id}/assign`
- `POST /{defect_id}/status`

### Incidents (`/api/incidents`)
- `POST /`
- `GET /`
- `POST /{incident_id}/create-task`

### Dashboard (`/api/dashboard` + WS)
- `GET /stats`
- `GET /observations`
- `WEBSOCKET /ws/dashboard`

### Approvals/Compliance (`/api/approvals`)
- `POST /`
- `GET /`
- `GET /audit-export`

### Reporting (`/api/reporting`)
- `GET /overview`
- `GET /closure-rate`
- `GET /device-utilization`
- `POST /export`

### UI (no API prefix)
- `GET /ui`
- `GET /ui/inspection`
- `GET /ui/inspection/tasks/{task_id}`
- `GET /ui/defects`
- `GET /ui/emergency`
- `GET /ui/command-center`

## 5. Background Jobs or Event Flows
No dedicated worker process (no Celery/RQ scheduler) is defined. Current asynchronous/event-driven flows:

- Telemetry ingest flow:
  - `POST /api/telemetry/ingest` -> write latest state to Redis (`state:{tenant}:{drone}`)
  - emit `telemetry.normalized` event (persisted in `events` table)
  - evaluate alert rules -> create/update alert rows -> emit `alert.created` when new
  - broadcast telemetry to `/ws/drones` subscribers.
- Command flow:
  - command request persisted (`command_requests`, PENDING)
  - emit `command.requested`
  - adapter async send + ACK timeout handling
  - update status to `ACKED`/`FAILED`/`TIMEOUT`
  - emit `command.acked` / `command.failed` / `command.timeout`.
- Mission flow:
  - create/update/approve/reject/transition mission states
  - emit mission events (`mission.created`, `mission.updated`, `mission.approved`, `mission.rejected`, `mission.state_changed`).
- Inspection/defect/incident/compliance flows emit domain events:
  - `inspection.template.created`, `inspection.task.created`, `inspection.observation.created`, `inspection.export.created`
  - `defect.created`, `defect.assigned`, `defect.status_changed`
  - `incident.created`, `incident.task_created`
  - `approval.recorded`
- Dashboard WebSocket flow:
  - `/ws/dashboard` pushes stats + marker updates in a 2-second loop.
- Audit flow:
  - write methods (`POST/PUT/PATCH/DELETE`) pass through `AuditMiddleware` and persist `audit_logs` entries.

## 6. Docker Services Definition
Two compose files are present.

### `docker-compose.yml` (root)
- `db`
  - image: `postgis/postgis:16-3.4`
  - ports: `${DB_PORT:-5432}:5432`
  - env: `POSTGRES_DB/USER/PASSWORD`
  - healthcheck: `pg_isready`
- `redis`
  - image: `redis:7-alpine`
  - ports: `${REDIS_PORT:-6379}:6379`
  - healthcheck: `redis-cli ping`
- `app`
  - build: `Dockerfile`
  - ports: `${APP_PORT:-8000}:8000`
  - command: `uvicorn app.main:app --host 0.0.0.0 --port 8000`
  - env: `DATABASE_URL`, `REDIS_URL`, `JWT_SECRET`, `JWT_ALGORITHM`
  - depends on healthy `db` + `redis`

### `infra/docker-compose.yml`
- includes `db`, `redis`, `app` (same roles as above, build context `..`), plus:
- `app-tools`
  - build from repo root, `working_dir: /work`
  - mounts repo `..:/work`
  - used by Makefile tasks for migration/openapi/e2e scripts
- `openapi-generator`
  - image: `openapitools/openapi-generator-cli:v7.10.0`
  - mount repo at `/work`

## 7. Current Migrations Status
- Alembic config: `alembic.ini` with `script_location = infra/migrations`.
- Migration chain is linear (no branches):
  - `202602190001` (`down_revision=None`)
  - `202602190002` -> `202602190001`
  - `202602190003` -> `202602190002`
  - `202602190004` -> `202602190003`
  - `202602190005` -> `202602190004`
  - `202602190006` -> `202602190005`
  - `202602210007` -> `202602190006`
- Repository migration head revision: `202602210007` (`202602210007_phase1_to_phase6.py`).
- Runtime DB revision in a live database was not directly queried in this snapshot (host lacks local `alembic` executable; project migration path is `make migrate` via Docker).

## 8. Known TODO / FIXME Markers in Code
Scan scope: `app/`, `tests/`, `infra/`.

- No `TODO` markers found.
- No `FIXME` markers found.

## 9. Test Coverage Summary (if available)
- Coverage tooling is not configured in repo configs:
  - no `pytest-cov`/`--cov` in `pyproject.toml`, `requirements-dev.txt`, `Makefile`, or CI workflow.
  - no coverage artifacts found (`.coverage`, `coverage.xml`, `htmlcov/`).
- Test suite inventory:
  - test files: 9
  - discovered `test_` functions: 23
  - files: `tests/test_adapters.py`, `tests/test_alert.py`, `tests/test_command.py`, `tests/test_events.py`, `tests/test_health.py`, `tests/test_identity.py`, `tests/test_mission.py`, `tests/test_registry.py`, `tests/test_telemetry.py`
- CI runs `make test` (plus lint/typecheck/migrate/openapi/e2e), but does not publish a coverage percentage.

## 10. Git Branch + Last 10 Commits Summary
- Current branch: `main`
- Last 10 commits:

| Commit | Date | Author | Message |
|---|---|---|---|
| `2a74e37` | 2026-02-21 | wxx | 修改 脚 |
| `93a61a7` | 2026-02-21 | wxx | 城市低空综合治理（城管巡查 B + 应急指挥 A）融合路线图 |
| `1900ea2` | 2026-02-21 | wxx | 用规范驱动的自动工程代理系统 |
| `9f8fa70` | 2026-02-20 | wxx | Phase 9 |
| `4f6a266` | 2026-02-20 | wxx | Phase 8 |
| `ebb64d3` | 2026-02-20 | wxx | Phase 7 |
| `1bddc78` | 2026-02-20 | wxx | Phase 6 |
| `c6f31b2` | 2026-02-20 | wxx | Phase 5 |
| `4a9ac64` | 2026-02-20 | wxx | Phase 4 |
| `f329dd8` | 2026-02-20 | wxx | Phase 3 |

High-level trend: recent commits include phase milestone progression (`Phase 3` through `Phase 9`) followed by roadmap/process documentation updates.

