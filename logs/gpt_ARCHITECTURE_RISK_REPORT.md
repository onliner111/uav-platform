# GPT Architecture Risk Report

Date: 2026-02-24
Scope: `app/`, `infra/`, `tests/`, `governance/`, `phases/`, `logs/`.

## Tight Coupling Areas

1. Command service is coupled to concrete adapter classes.
- Evidence: `app/services/command_service.py:12-14`, `app/services/command_service.py:55-58`.
- Risk: adding/changing vendor integration requires core service edits.

2. Telemetry ingest is tightly coupled to Redis write + event publish + alert evaluation in one call path.
- Evidence: `app/services/telemetry_service.py:25`, `app/services/telemetry_service.py:29-35`.
- Risk: one dependency failure can degrade the whole ingest path.

3. UI router bypasses shared API dependency-based authz model.
- Evidence: `app/api/routers/ui.py:21-30`, `app/api/deps.py:24-42`.
- Risk: authorization behavior diverges from API routers.

4. Eventing uses process-local singleton bus and inline handler execution.
- Evidence: `app/infra/events.py:15`, `app/infra/events.py:47-48`, `app/infra/events.py:61`.
- Risk: no distribution/replay semantics and request-thread coupling to handlers.

5. Reporting and dashboard services are coupled to full-entity reads and in-memory aggregation.
- Evidence: `app/services/reporting_service.py:31-33`, `app/services/reporting_service.py:55-57`, `app/services/dashboard_service.py:25-27`.
- Risk: scaling data volume increases memory and latency sharply.

## Violations of governance/AGENTS.md rules

1. Per-phase report protocol is not consistently followed for completed phase 07a/07b items.
- Rule: `phases/reporting.md:15` requires `logs/<phase-name>.report.md` on success.
- Evidence: `logs/PROGRESS.md:13-16` marks 07a/07b done, but `logs/*.report.md` contains only phases 01-06 and 07c.

2. Critical export/download reads are excluded from audit logging.
- Rule: `governance/AGENTS.md` Government Mode requires critical actions (including export) logged to audit.
- Evidence: GET export/download endpoints at `app/api/routers/tenant_export.py:70-100` and `app/api/routers/approval.py` (`/audit-export`) are GET; audit middleware logs only write methods (`app/infra/audit.py:13`, `app/infra/audit.py:43`).

3. UI endpoints do not enforce RBAC permissions via `require_perm`.
- Rule: `governance/AGENTS.md` requires integration with existing RBAC.
- Evidence: UI routes rely on token decode only (`app/api/routers/ui.py:21-30`, `app/api/routers/ui.py:33-107`) and do not use `Depends(require_perm(...))`.

4. Event integrity is incomplete for some business mutations.
- Rule: `governance/AGENTS.md` says business state changes MUST generate events.
- Evidence: delete paths without event publish in `app/services/registry_service.py:107` and `app/services/mission_service.py:166`.

5. Strict tenant-column rule has unresolved conflict with global identity tables.
- Rule: `governance/AGENTS.md` says all new tables must include `tenant_id`.
- Evidence: `Permission` and `RolePermission` tables have no `tenant_id` (`app/domain/models.py:89`, `app/domain/models.py:121`).
- Note: `governance/tenant_boundary_matrix.md` documents some global-model exceptions, so this is a governance consistency issue.

## Potential Scalability Risks

1. Dashboard websocket loop executes DB-backed stats + observations every 2s per connection.
- Evidence: `app/api/routers/dashboard.py:87-88`, `app/api/routers/dashboard.py:105`, `app/services/dashboard_service.py:23-46`.

2. Request/response command dispatch waits on adapter ACK inside API lifecycle.
- Evidence: `app/services/command_service.py:190`.

3. Tenant export reads whole table result sets into memory before file write.
- Evidence: `app/services/tenant_export_service.py:123`, `app/services/tenant_export_service.py:157`.

4. Reporting overview/utilization reads full mission/inspection/defect/drone collections.
- Evidence: `app/services/reporting_service.py:31-33`, `app/services/reporting_service.py:55-57`.

5. Identity permission collection scans global role-permission and permission tables and filters in Python.
- Evidence: `app/services/identity_service.py:388-395`.

6. Telemetry fanout hub is in-memory per process.
- Evidence: `app/api/routers/telemetry.py:19`, `app/api/routers/telemetry.py:32`.

## Data Model Design Risks

1. Tenant boundary work is still partial in several domains.
- Evidence: `governance/tenant_boundary_matrix.md:20-23` (Inspection/Defect/Incident/Alert marked PARTIAL or IN-PROGRESS).

2. Registry credential lineage is high-risk and still incomplete.
- Evidence: `governance/tenant_boundary_matrix.md:26` (HIGH risk, PLANNED lookup/tests).

3. Single-column FK patterns remain in tenant-owned relationships.
- Evidence: table definitions around `app/domain/models.py:154` (`DroneCredential`), `app/domain/models.py:210` (`Approval`), `app/domain/models.py:666` (`InspectionTask`), `app/domain/models.py:690` (`InspectionObservation`), `app/domain/models.py:709` (`InspectionExport`), `app/domain/models.py:720` (`Defect`).

4. Geospatial fields are plain strings (`area_geom`, `location_geom`) rather than typed geometry columns.
- Evidence: `app/domain/models.py` (`InspectionTask`, `Incident`).

5. Heavy JSON columns (`payload`, `constraints`, `detail`, `capabilities`) increase schema drift risk.
- Evidence: mission/alert/drone/command entities in `app/domain/models.py`.

## Permission Model Weaknesses

1. Password hashing uses static-salt SHA-256 instead of adaptive KDF.
- Evidence: `app/services/identity_service.py:51-52`.

2. JWT secret has insecure default fallback.
- Evidence: `app/infra/auth.py:9`.

3. Export/purge endpoints require wildcard permission only, without dedicated scoped permissions.
- Evidence: `app/api/routers/tenant_export.py:52`, `app/api/routers/tenant_purge.py:86`, `app/api/routers/tenant_purge.py:104`.

4. UI access checks tenant-bearing token but not per-page permissions.
- Evidence: `app/api/routers/ui.py:21-30`, `app/api/routers/ui.py:33-107`.

5. Token accepted via query string on UI/WS endpoints increases leakage risk.
- Evidence: `app/api/routers/ui.py:33`, `app/api/routers/telemetry.py:94`, `app/api/routers/dashboard.py:65`.

6. Tenant creation/bootstrap endpoints are open API routes (no `require_perm` dependency), relying on deployment trust assumptions.
- Evidence: `app/api/routers/identity.py:50`, `app/api/routers/identity.py:117`, contrasted with protected identity routes starting `app/api/routers/identity.py:63`.

## Missing Test Coverage Areas

1. No dedicated dashboard API/websocket test module.
- Evidence: tests directory has no `test_dashboard.py`; dashboard websocket is at `app/api/routers/dashboard.py:65-109`.

2. No dedicated UI router tests.
- Evidence: tests directory has no `test_ui.py`; UI routes at `app/api/routers/ui.py:33-107`.

3. Incident tests currently emphasize DB constraint behavior, with limited API lifecycle coverage.
- Evidence: `tests/test_incident.py` currently contains DB-boundary-focused case(s), and boundary matrix flags incident tests IN-PROGRESS (`governance/tenant_boundary_matrix.md:22`).

4. Reporting coverage is narrow relative to endpoint surface.
- Evidence: only one reporting test in `tests/test_reporting.py:85`, while API exposes multiple endpoints including export (`app/api/routers/reporting.py`).

5. Approval/audit export route behavior is not explicitly tested.
- Evidence: approval tests in `tests/test_compliance.py` focus list + FK enforcement; no direct `/api/approvals/audit-export` assertions.

6. Websocket negative auth cases are untested (invalid/expired token, missing permission).
- Evidence: telemetry websocket happy-path test at `tests/test_telemetry.py:119`; no 4401/4403 assertion tests found.

7. No coverage percentage instrumentation is configured.
- Evidence: `pyproject.toml` pytest addopts is `-q` only; no `--cov` settings or coverage artifacts present.

## Dangerous Technical Debt

1. Governance artifact drift risk: phase completion tracked in `logs/PROGRESS.md`, but required per-phase report file generation is inconsistent for 07a/07b.
- Evidence: `logs/PROGRESS.md:13-16`, `phases/reporting.md:15`.

2. Monolithic `models.py` mixes persistence models and API DTOs in one large file.
- Evidence: `app/domain/models.py` (single high-churn module across many domains).

3. In-process event bus has no durable transport, retry, or outbox semantics.
- Evidence: `app/infra/events.py:26-48`.

4. File-system based exports/reports (`logs/exports`, `logs/purge`) are local-node artifacts.
- Evidence: `app/services/reporting_service.py:77-80`, `app/services/tenant_export_service.py:27-33`, `app/services/tenant_purge_service.py:48-52`.

5. Authorization model depends on token-embedded permission snapshots and wildcard shortcuts.
- Evidence: `app/infra/auth.py:26`, `app/api/routers/tenant_export.py:52`, `app/api/routers/tenant_purge.py:86`.

6. Dashboard and reporting paths are likely to become bottlenecks without DB-side aggregation/index tuning.
- Evidence: `app/services/dashboard_service.py:25-27`, `app/services/reporting_service.py:31-33`, `app/services/reporting_service.py:55-57`.

## Suggested Priority Order

1. Close governance and audit compliance gaps (phase report artifacts, export-read auditing, UI RBAC parity).
2. Finish remaining tenant-boundary DB constraints highlighted in `tenant_boundary_matrix.md`.
3. Harden auth primitives (password KDF, JWT secret policy, token transport).
4. Add missing dashboard/UI/incident/reporting-export/websocket-negative tests and coverage instrumentation.
5. Plan scalability refactor for dashboard/reporting queries and event delivery semantics.
