# GPT System Snapshot

Generated: 2026-02-22
Repository: `C:\codex\uav-platform`

## 1. Project Structure Tree (max depth 4)

```text
.
|-- .github
|   |-- workflows
|   |   `-- ci.yml
|-- app
|   |-- adapters
|   |   |-- __init__.py
|   |   |-- base.py
|   |   |-- dji_adapter.py
|   |   |-- fake_adapter.py
|   |   `-- mavlink_adapter.py
|   |-- api
|   |   |-- routers
|   |   |   |-- __init__.py
|   |   |   |-- alert.py
|   |   |   |-- approval.py
|   |   |   |-- command.py
|   |   |   |-- dashboard.py
|   |   |   |-- defect.py
|   |   |   |-- identity.py
|   |   |   |-- incident.py
|   |   |   |-- inspection.py
|   |   |   |-- mission.py
|   |   |   |-- registry.py
|   |   |   |-- reporting.py
|   |   |   |-- telemetry.py
|   |   |   `-- ui.py
|   |   |-- __init__.py
|   |   `-- deps.py
|   |-- domain
|   |   |-- __init__.py
|   |   |-- models.py
|   |   |-- permissions.py
|   |   `-- state_machine.py
|   |-- infra
|   |   |-- __init__.py
|   |   |-- audit.py
|   |   |-- auth.py
|   |   |-- db.py
|   |   |-- events.py
|   |   |-- migrate.py
|   |   |-- openapi_export.py
|   |   |-- redis_state.py
|   |   `-- tenant.py
|   |-- services
|   |   |-- __init__.py
|   |   |-- alert_service.py
|   |   |-- command_service.py
|   |   |-- compliance_service.py
|   |   |-- dashboard_service.py
|   |   |-- defect_service.py
|   |   |-- identity_service.py
|   |   |-- incident_service.py
|   |   |-- inspection_service.py
|   |   |-- mission_service.py
|   |   |-- registry_service.py
|   |   |-- reporting_service.py
|   |   `-- telemetry_service.py
|   |-- web
|   |   |-- static
|   |   |   |-- command_center.js
|   |   |   |-- defects.js
|   |   |   |-- emergency.js
|   |   |   |-- inspection_task.js
|   |   |   `-- ui.css
|   |   `-- templates
|   |       |-- command_center.html
|   |       |-- defects.html
|   |       |-- emergency.html
|   |       |-- inspection_list.html
|   |       `-- inspection_task_detail.html
|   |-- __init__.py
|   `-- main.py
|-- docs
|   |-- Admin_Manual_V1.0.md
|   |-- Admin_Manual_V2.0.md
|   |-- API_Appendix_V2.0.md
|   |-- Architecture_Overview_V1.0.md
|   |-- Architecture_Overview_V2.0.md
|   |-- Deployment_Guide_V1.0.md
|   |-- Deployment_Guide_V2.0.md
|   |-- SYSTEM_SNAPSHOT.md
|   |-- User_Manual_V1.0.md
|   `-- User_Manual_V2.0.md
|-- gpt
|   |-- gen_report1.sh
|   `-- gen_report2.sh
|-- infra
|   |-- migrations
|   |   |-- versions
|   |   |   |-- 202602190001_init_phase0.py
|   |   |   |-- 202602190002_identity_phase1.py
|   |   |   |-- 202602190003_registry_phase2.py
|   |   |   |-- 202602190004_mission_phase3.py
|   |   |   |-- 202602190005_command_phase5.py
|   |   |   |-- 202602190006_alert_phase7.py
|   |   |   `-- 202602210007_phase1_to_phase6.py
|   |   |-- env.py
|   |   `-- script.py.mako
|   |-- scripts
|   |   |-- demo_command_center_phase4.py
|   |   |-- demo_common.py
|   |   |-- demo_compliance_phase5.py
|   |   |-- demo_defect_phase2.py
|   |   |-- demo_e2e.py
|   |   |-- demo_emergency_phase3.py
|   |   |-- demo_inspection_phase1.py
|   |   |-- demo_reporting_phase6.py
|   |   |-- run_all_phases.sh
|   |   |-- verify_all.sh
|   |   |-- verify_openapi_client.py
|   |   `-- verify_smoke.py
|   `-- docker-compose.yml
|-- logs
|   |-- phase-01-inspection.md.report.md
|   |-- phase-02-defect-closure.md.report.md
|   |-- phase-03-emergency.md.report.md
|   |-- phase-04-command-center.md.report.md
|   |-- phase-05-compliance.md.report.md
|   |-- phase-06-reporting.md.report.md
|   |-- PROGRESS.md
|   `-- README.md
|-- openapi
|   `-- clients
|       `-- .gitkeep
|-- phases
|   |-- index.md
|   |-- phase-01-inspection.md
|   |-- phase-02-defect-closure.md
|   |-- phase-03-emergency.md
|   |-- phase-04-command-center.md
|   |-- phase-05-compliance.md
|   |-- phase-06-reporting.md
|   |-- reporting.md
|   |-- resume.md
|   `-- state.md
|-- tests
|   |-- test_adapters.py
|   |-- test_alert.py
|   |-- test_command.py
|   |-- test_events.py
|   |-- test_health.py
|   |-- test_identity.py
|   |-- test_mission.py
|   |-- test_registry.py
|   `-- test_telemetry.py
|-- .env.example
|-- .gitignore
|-- [app
|-- [internal]
|-- 11.10.1
|-- governance/AGENTS.md
|-- alembic.ini
|-- governance/EXECUTION_PLAYBOOK.md
|-- docker-compose.yml
|-- Dockerfile
|-- Makefile
|-- pyproject.toml
|-- requirements-dev.txt
|-- requirements.txt
`-- governance/ROADMAP.md
```

## 2. Main Modules and Responsibilities

- `app/main.py`: FastAPI app bootstrap, router registration, static mount, health/ready endpoints, audit middleware wiring.
- `app/api/routers/*`: HTTP and WebSocket API layer; auth/permission checks and request/response schema binding.
- `app/services/*`: Core business logic per domain (identity, registry, mission, telemetry, command, alert, inspection, defect, incident, dashboard, compliance, reporting).
- `app/domain/models.py`: SQLModel table models + Pydantic request/response contracts.
- `app/domain/permissions.py` and `app/domain/state_machine.py`: RBAC permission constants/checks and mission state transitions.
- `app/infra/*`: DB engine/session, JWT auth helpers, tenant request context, audit logging middleware, in-process event bus, Redis state access, migration/openapi helpers.
- `app/adapters/*`: Plugin-style adapter layer (`FakeAdapter`, `MavlinkAdapter`, `DjiAdapter`) behind protocol contracts in `base.py`.
- `app/web/templates` + `app/web/static`: Embedded demo UI (Jinja2 + static JS/CSS).
- `infra/migrations/*`: Alembic migration environment and revision files.
- `infra/scripts/*`: Phase demos, smoke verification, end-to-end scripts.
- `tests/*`: Pytest functional/unit tests for adapters, health, identity, registry, mission, telemetry, command, alerts, event bus.

## 3. Database Models (tables + fields)

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

Base health:
- `GET /healthz`
- `GET /readyz`

Identity (`/api/identity`):
- `POST /tenants`, `GET /tenants`, `GET /tenants/{tenant_id}`, `PATCH /tenants/{tenant_id}`, `DELETE /tenants/{tenant_id}`
- `POST /bootstrap-admin`, `POST /dev-login`
- `POST /users`, `GET /users`, `GET /users/{user_id}`, `PATCH /users/{user_id}`, `DELETE /users/{user_id}`
- `POST /roles`, `GET /roles`, `GET /roles/{role_id}`, `PATCH /roles/{role_id}`, `DELETE /roles/{role_id}`
- `POST /permissions`, `GET /permissions`, `GET /permissions/{permission_id}`, `PATCH /permissions/{permission_id}`, `DELETE /permissions/{permission_id}`
- `POST /users/{user_id}/roles/{role_id}`, `DELETE /users/{user_id}/roles/{role_id}`
- `POST /roles/{role_id}/permissions/{permission_id}`, `DELETE /roles/{role_id}/permissions/{permission_id}`

Registry (`/api/registry`):
- `POST /drones`, `GET /drones`, `GET /drones/{drone_id}`, `PATCH /drones/{drone_id}`, `DELETE /drones/{drone_id}`

Mission (`/api/mission`):
- `POST /missions`, `GET /missions`, `GET /missions/{mission_id}`, `PATCH /missions/{mission_id}`, `DELETE /missions/{mission_id}`
- `POST /missions/{mission_id}/approve`, `GET /missions/{mission_id}/approvals`, `POST /missions/{mission_id}/transition`

Telemetry (`/api/telemetry` + WS):
- `POST /ingest`, `GET /drones/{drone_id}/latest`
- `WEBSOCKET /ws/drones`

Command (`/api/command`):
- `POST /commands`, `GET /commands`, `GET /commands/{command_id}`

Alert (`/api/alert`):
- `GET /alerts`, `GET /alerts/{alert_id}`, `POST /alerts/{alert_id}/ack`, `POST /alerts/{alert_id}/close`

Inspection (`/api/inspection`):
- `GET /templates`, `POST /templates`, `GET /templates/{template_id}`
- `POST /templates/{template_id}/items`, `GET /templates/{template_id}/items`
- `POST /tasks`, `GET /tasks`, `GET /tasks/{task_id}`
- `POST /tasks/{task_id}/observations`, `GET /tasks/{task_id}/observations`
- `POST /tasks/{task_id}/export`, `GET /exports/{export_id}`

Defects (`/api/defects`):
- `POST /from-observation/{observation_id}`
- `GET /api/defects`
- `GET /stats`
- `GET /{defect_id}`
- `POST /{defect_id}/assign`
- `POST /{defect_id}/status`

Incidents (`/api/incidents`):
- `POST /api/incidents`, `GET /api/incidents`, `POST /api/incidents/{incident_id}/create-task`

Dashboard (`/api/dashboard` + WS):
- `GET /stats`, `GET /observations`
- `WEBSOCKET /ws/dashboard`

Approvals/Compliance (`/api/approvals`):
- `POST /api/approvals`, `GET /api/approvals`, `GET /api/approvals/audit-export`

Reporting (`/api/reporting`):
- `GET /overview`, `GET /closure-rate`, `GET /device-utilization`, `POST /export`

Embedded UI routes:
- `GET /ui`, `GET /ui/inspection`, `GET /ui/inspection/tasks/{task_id}`
- `GET /ui/defects`, `GET /ui/emergency`, `GET /ui/command-center`

## 5. Background Jobs or Event Flows

Background jobs:
- No separate worker queue (no Celery/RQ/cron process found in repo).
- Background-like behavior exists in WebSocket loops only:
  - `ws_dashboard`: pushes stats/markers every 2 seconds.
  - `ws_drones`: broadcasts on telemetry ingest events.

Event flow backbone:
- `EventBus` (`app/infra/events.py`) persists all published events into `events` table, then invokes in-process subscribers.

Primary business event flows:
- Telemetry: `POST /api/telemetry/ingest` -> Redis latest state -> `telemetry.normalized` event -> alert rule evaluation.
- Alert lifecycle: telemetry rule hit -> `alert.created`; actions -> `alert.acked` / `alert.closed`.
- Command lifecycle: command persisted as `PENDING` -> `command.requested` -> adapter ACK path -> `command.acked` or failure path (`command.failed`, `command.timeout`).
- Mission lifecycle: `mission.created`, `mission.updated`, `mission.approved`/`mission.rejected`, `mission.state_changed`.
- Inspection lifecycle: `inspection.template.created`, `inspection.task.created`, `inspection.observation.created`, `inspection.export.created`.
- Defect lifecycle: `defect.created`, `defect.assigned`, `defect.status_changed`.
- Incident lifecycle: `incident.created`, `incident.task_created`.
- Compliance lifecycle: `approval.recorded`.

Audit flow:
- Write HTTP methods (`POST/PUT/PATCH/DELETE`) are captured by `AuditMiddleware` and persisted in `audit_logs`.

## 6. Docker Services Definition

`docker-compose.yml` (repo root):
- `db`: `postgis/postgis:16-3.4`, exposes `DB_PORT:5432`, healthcheck `pg_isready`.
- `redis`: `redis:7-alpine`, exposes `REDIS_PORT:6379`, healthcheck `redis-cli ping`.
- `app`: built from `Dockerfile`, exposes `APP_PORT:8000`, command `uvicorn app.main:app --host 0.0.0.0 --port 8000`, depends on healthy `db` and `redis`.

`infra/docker-compose.yml`:
- Includes `db`, `redis`, `app` (same functional role, build context `..`).
- Adds `app-tools`: utility container for scripts/tests/openapi generation.
- Adds `openapi-generator`: `openapitools/openapi-generator-cli:v7.10.0`.

Common env used by app services:
- `DATABASE_URL`, `REDIS_URL`, `JWT_SECRET`, `JWT_ALGORITHM`.

## 7. Current Migrations Status

Alembic revision chain (linear, single branch):
- `202602190001` (init phase0) ->
- `202602190002` (identity phase1) ->
- `202602190003` (registry phase2) ->
- `202602190004` (mission phase3) ->
- `202602190005` (command phase5) ->
- `202602190006` (alert phase7) ->
- `202602210007` (inspection/defect/emergency/compliance/reporting)

Head revision from migration files:
- `202602210007`

Runtime DB-applied revision:
- Not confirmed in this snapshot environment (local `alembic` CLI not installed; Docker daemon access denied in sandbox for `docker compose ps`/runtime checks).

## 8. Known TODO / FIXME Markers in Code

Search scope: `app`, `tests`, `infra`, `docs`

Result:
- No `TODO` markers found in application code.
- No `FIXME` markers found in application code.
- Existing matches are documentation text in `docs/SYSTEM_SNAPSHOT.md` only.

## 9. Test Coverage Summary (if available)

- Coverage tooling is not configured:
  - No `pytest-cov` in `requirements-dev.txt`.
  - No `--cov` in `pyproject.toml` pytest options.
  - No coverage output artifacts found (`.coverage`, `coverage.xml`, `htmlcov/`).
- Available test suite snapshot:
  - `9` test files under `tests/`.
  - `23` discovered `test_*` functions.
- CI workflow (`.github/workflows/ci.yml`) runs `make lint`, `make typecheck`, `make test`, `make migrate`, `make openapi`, `make openapi-smoke`, `make e2e`.

## 10. Git Branch + Last 10 Commits Summary

Current branch:
- `main`

Last 10 commits:
- `3e3e7b6` | 2026-02-22 | Wangxx | report to gpt
- `2a74e37` | 2026-02-21 | wxx | 修改 脚
- `93a61a7` | 2026-02-21 | wxx | 城市低空综合治理（城管巡查 B + 应急指挥 A）融合路线图
- `1900ea2` | 2026-02-21 | wxx | 用规范驱动的自动工程代理系统
- `9f8fa70` | 2026-02-20 | wxx | Phase 9
- `4f6a266` | 2026-02-20 | wxx | Phase 8
- `ebb64d3` | 2026-02-20 | wxx | Phase 7
- `1bddc78` | 2026-02-20 | wxx | Phase 6
- `c6f31b2` | 2026-02-20 | wxx | Phase 5
- `4a9ac64` | 2026-02-20 | wxx | Phase 4

