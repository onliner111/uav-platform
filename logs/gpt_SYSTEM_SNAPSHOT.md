# GPT System Snapshot

Generated on: 2026-02-24
Repository root: `C:\codex\uav-platform`

## 1. Project Structure Tree (max depth 4)
```text
.
- .env.example
- .github
  - workflows
    - ci.yml
- .gitignore
- alembic.ini
- app
  - adapters
    - base.py
    - dji_adapter.py
    - fake_adapter.py
    - mavlink_adapter.py
  - api
    - deps.py
    - routers
      - alert.py
      - approval.py
      - command.py
      - dashboard.py
      - defect.py
      - identity.py
      - incident.py
      - inspection.py
      - mission.py
      - registry.py
      - reporting.py
      - telemetry.py
      - tenant_export.py
      - tenant_purge.py
      - ui.py
  - domain
    - models.py
    - permissions.py
    - state_machine.py
  - infra
    - audit.py
    - auth.py
    - db.py
    - events.py
    - migrate.py
    - openapi_export.py
    - redis_state.py
    - tenant.py
  - services
    - alert_service.py
    - command_service.py
    - compliance_service.py
    - dashboard_service.py
    - defect_service.py
    - identity_service.py
    - incident_service.py
    - inspection_service.py
    - mission_service.py
    - registry_service.py
    - reporting_service.py
    - telemetry_service.py
    - tenant_export_service.py
    - tenant_purge_service.py
  - web
    - static
      - command_center.js
      - defects.js
      - emergency.js
      - inspection_task.js
      - ui.css
    - templates
      - command_center.html
      - defects.html
      - emergency.html
      - inspection_list.html
      - inspection_task_detail.html
  - main.py
- docs
  - Admin_Manual_V2.0.md
  - API_Appendix_V2.0.md
  - Architecture_Overview_V2.0.md
  - Deployment_Guide_V2.0.md
  - PROJECT_STATUS.md
  - User_Manual_V2.0.md
  - ops
    - TENANT_EXPORT.md
    - TENANT_PURGE.md
- governance
  - 00_INDEX.md
  - 01_GOVERNANCE.md
  - 02_REPO_LAYOUT.md
  - 03_PHASE_LIFECYCLE.md
  - 04_CHAT_INTERACTION_PROTOCOL.md
  - 05_GOVERNANCE_CONSISTENCY_CHECKLIST.md
  - AGENTS.md
  - EXECUTION_PLAYBOOK.md
  - ROADMAP.md
  - tenant_boundary_matrix.md
- infra
  - docker-compose.yml
  - migrations
    - env.py
    - script.py.mako
    - versions
      - 202602190001_init_phase0.py
      - ...
      - 202602240028_phase07b_b5_reporting_export_enforce.py
  - scripts
    - demo_command_center_phase4.py
    - demo_common.py
    - demo_compliance_phase5.py
    - demo_defect_phase2.py
    - demo_e2e.py
    - demo_emergency_phase3.py
    - demo_inspection_phase1.py
    - demo_reporting_phase6.py
    - run_all_phases.sh
    - verify_all.sh
    - verify_openapi_client.py
    - verify_smoke.py
- logs
  - GOVERNANCE_AUDIT.md
  - PROGRESS.md
  - gpt_ARCHITECTURE_RISK_REPORT.md
  - gpt_SYSTEM_SNAPSHOT.md
  - phase-01-inspection.md.report.md
  - ...
  - phase-07c-tenant-export-purge.md.report.md
- openapi
  - openapi.json
  - clients
    - .gitkeep
    - python
      - docs/
      - openapi_client/
      - test/
      - pyproject.toml
      - README.md
  - postman
    - .openapi-generator/
    - .openapi-generator-ignore
    - postman.json
- phases
  - index.md
  - phase-01-inspection.md
  - ...
  - phase-07c-tenant-export-purge.md
  - reporting.md
  - resume.md
  - state.md
- tests
  - test_adapters.py
  - test_alert.py
  - test_command.py
  - test_compliance.py
  - test_defect.py
  - test_events.py
  - test_health.py
  - test_identity.py
  - test_incident.py
  - test_inspection.py
  - test_mission.py
  - test_registry.py
  - test_reporting.py
  - test_telemetry.py
  - test_tenant_export.py
  - test_tenant_purge_dry_run.py
  - test_tenant_purge_execute.py
- tooling
  - gpt
    - gen_report.sh
- Dockerfile
- Makefile
- pyproject.toml
- README.md
- requirements-dev.txt
- requirements.txt
```

## 2. List of Main Modules and Responsibilities
- `app/main.py`: FastAPI app bootstrap, middleware, router registration, health/readiness endpoints.
- `app/api/routers/*`: Domain API entry points (identity, registry, mission, telemetry, command, alert, inspection, defect, incident, dashboard, approvals, reporting, tenant export/purge, UI).
- `app/api/deps.py`: token decode dependency + permission gate (`require_perm`).
- `app/services/*`: domain business logic and persistence orchestration.
- `app/domain/models.py`: SQLModel entities (DB tables), enums, and API DTO schemas.
- `app/infra/*`: DB engine/session, JWT auth, audit middleware, event bus, Redis state, tenant context.
- `app/adapters/*`: UAV adapter abstraction and vendor implementations (Fake/MAVLink/DJI).
- `infra/migrations/*`: Alembic migration environment and revision scripts.
- `infra/docker-compose.yml`: runtime topology for db/redis/app/tooling.
- `tests/*`: API and domain regression tests.
- `governance/*` and `phases/*`: execution governance, boundary matrix, phase specs, checkpoint state.

## 3. Database Models (tables + fields)
`app/domain/models.py` SQLModel `table=True` entities:
- `events`: `event_id`, `event_type`, `tenant_id`, `ts`, `actor_id`, `correlation_id`, `payload`
- `audit_logs`: `id`, `tenant_id`, `actor_id`, `action`, `resource`, `method`, `status_code`, `ts`, `detail`
- `tenants`: `id`, `name`, `created_at`
- `users`: `id`, `tenant_id`, `username`, `password_hash`, `is_active`, `created_at`
- `roles`: `id`, `tenant_id`, `name`, `description`, `created_at`
- `permissions`: `id`, `name`, `description`, `created_at`
- `user_roles`: `tenant_id`, `user_id`, `role_id`, `created_at`
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
Source: `openapi/openapi.json` + websocket routers.

- Total HTTP endpoints: **92**
- Tag groups:
  - `identity` (26)
  - `inspection` (12)
  - `mission` (8)
  - `defects` (6)
  - `ui` (6)
  - `registry` (5)
  - `alert` (4)
  - `reporting` (4)
  - `command` (3)
  - `approvals` (3)
  - `incidents` (3)
  - `tenant-export` (3)
  - `tenant-purge` (3)
  - `dashboard` (2)
  - `telemetry` (2)
  - `untagged` (2: `/healthz`, `/readyz`)
- WebSocket endpoints (not in OpenAPI):
  - `/ws/drones` (telemetry stream)
  - `/ws/dashboard` (dashboard stats/markers stream)

## 5. Background Jobs or Event Flows
No external job queue/worker process is defined; flows are in-process.

- Telemetry flow:
  - `POST /api/telemetry/ingest` -> Redis latest state write -> `telemetry.normalized` event -> alert evaluation -> WS broadcast.
- Command flow:
  - `POST /api/command/commands` -> idempotent DB record -> `command.requested` event -> adapter send with timeout -> status update -> `command.acked`/`command.failed`/`command.timeout` event.
- Inspection/Defect/Incident flow:
  - inspection events (`template/task/observation/export`) -> defect lifecycle events -> incident task creation event.
- Compliance flow:
  - `POST /api/approvals` writes `approval_records` + emits `approval.recorded`.
- Tenant export flow:
  - `POST /api/tenants/{tenant_id}/export` writes JSONL table dumps + manifest + optional zip under `logs/exports/...`.
- Tenant purge flow:
  - dry-run plan/count/token -> execute hard delete with confirmation -> verification -> report under `logs/purge/...`.
- Dashboard websocket loop:
  - `/ws/dashboard` polls DB every 2 seconds and pushes stats/markers.

## 6. Docker Services Definition
From `infra/docker-compose.yml`:

- `db`
  - Image: `postgis/postgis:16-3.4`
  - Port: `${DB_PORT:-5432}:5432`
  - Healthcheck: `pg_isready`
- `redis`
  - Image: `redis:7-alpine`
  - Port: `${REDIS_PORT:-6379}:6379`
  - Healthcheck: `redis-cli ping`
- `app`
  - Build: repository `Dockerfile`
  - Port: `${APP_PORT:-8000}:8000`
  - Depends on healthy `db` and `redis`
  - Command: `uvicorn app.main:app --host 0.0.0.0 --port 8000`
- `app-tools`
  - Build: repository `Dockerfile`
  - Working dir `/work`, volume mount `..:/work`
  - Used for tooling scripts, tests, migrations, exports
- `openapi-generator`
  - Image: `openapitools/openapi-generator-cli:v7.10.0`
  - Working dir `/work`, volume mount `..:/work`

## 7. Current Migrations Status
- Migration scripts present: **28** (`infra/migrations/versions`).
- Revision root: `202602190001` (`down_revision = None`).
- Current repository migration head: `202602240028` (`202602240028_phase07b_b5_reporting_export_enforce.py`).
- Migration chain shape: single linear head (no branch split detected).
- Runtime DB-applied revision: **not directly verified in this snapshot** (host `alembic` command unavailable in current shell).
- Phase checkpoint status (`phases/state.md`):
  - `current_phase: DONE`
  - `last_success_phase: phase-07c-tenant-export-purge.md`
  - `updated_at: 2026-02-24T12:46:47Z`

## 8. Known TODO / FIXME Markers in Code
Search scope: `app/`, `infra/`, `tests/`.

- No `TODO` or `FIXME` markers found.

## 9. Test Coverage Summary (if available)
- Test files: **17** (`tests/test_*.py`).
- Test functions: **43** (`def test_*`).
- Coverage artifacts/config:
  - No `.coverage`, `coverage.xml`, or `htmlcov/` artifacts found.
  - `pyproject.toml` pytest config uses `addopts = "-q"` (no `--cov` flags).
- Coverage percentage: **not available from repository artifacts**.
- Observed gaps from inventory:
  - no dedicated `tests/test_dashboard.py`
  - no dedicated `tests/test_ui.py`

## 10. Git Branch + Last 10 Commits Summary
- Current branch: `main`
- Last 10 commits:
  1. `aa19d1d` (2026-02-24 20:54:09 +0800, Wangxx): `07 done`
  2. `a3dff92` (2026-02-23 01:14:35 +0800, Wangxx): `Refactor repo structure: governance + tooling consolidation`
  3. `d52e98a` (2026-02-23 01:00:24 +0800, Wangxx): `Remove accidental placeholder files`
  4. `7877699` (2026-02-23 00:54:53 +0800, Wangxx): `Introduce governance documentation structure (SSOT model)`
  5. `3e3e7b6` (2026-02-22 23:36:11 +0800, Wangxx): `report to gpt`
  6. `2a74e37` (2026-02-21 19:46:56 +0800, wxx): `[non-ascii commit subject]`
  7. `93a61a7` (2026-02-21 12:47:06 +0800, wxx): `[non-ascii commit subject]`
  8. `1900ea2` (2026-02-21 01:47:04 +0800, wxx): `[non-ascii commit subject]`
  9. `9f8fa70` (2026-02-20 16:35:43 +0800, wxx): `Phase 9`
  10. `4f6a266` (2026-02-20 16:16:55 +0800, wxx): `Phase 8`

