# GPT Architecture Risk Report

Date: 2026-02-24  
Scope: `app/`, `infra/migrations/`, `tests/`, `governance/`, `phases/`, `logs/`, `Makefile`, `infra/scripts/`.

## Tight Coupling Areas

1. Command dispatch depends on concrete adapters in service code.
- Evidence: `app/services/command_service.py:12-14`, `app/services/command_service.py:55-59`.
- Risk: adapter expansion requires editing core service code, increasing change blast radius.

2. Telemetry ingest path is hard-coupled to alert evaluation and Redis writes.
- Evidence: `app/services/telemetry_service.py:27-35`.
- Risk: telemetry throughput and alert logic share failure/latency domain.

3. UI routes bypass shared API auth/permission dependency path.
- Evidence: `app/api/routers/ui.py:21-30`, `app/api/deps.py:16-42`.
- Risk: duplicated auth logic and inconsistent RBAC enforcement.

4. Eventing and audit rely on global singleton/global engine state.
- Evidence: `app/infra/events.py:61`, `app/infra/events.py:29`, `app/infra/audit.py:11`, `app/infra/db.py:15`.
- Risk: harder to isolate, shard, or scale behavior by deployment unit.

5. Data model and API schema live in one large module.
- Evidence: `app/domain/models.py` (~966 lines).
- Risk: high merge-conflict probability and weaker separation of concerns.

## Violations of governance/AGENTS.md Rules

1. Phase/checkpoint SSOT drift.
- Rule: `governance/AGENTS.md:170-180` (`phases/state.md` is SSOT and must be updated on phase success).
- Evidence: `phases/state.md:3-8` still ends at phase 06/DONE, while `logs/PROGRESS.md:13-14` records phase 07a work.
- Impact: execution state is internally inconsistent.

2. Required per-phase reporting not followed for phase 07 entries.
- Rule: `governance/AGENTS.md:71` and `phases/reporting.md:11-27`.
- Evidence: `logs/PROGRESS.md:13-14` references phase 07a success, but `logs/` contains only phase 01-06 report files.
- Impact: governance audit trail is incomplete.

3. Government Mode table rule conflict for identity tables.
- Rule: `governance/AGENTS.md:96`.
- Evidence: `app/domain/models.py:89-95` (`permissions`) and `app/domain/models.py:121-126` (`role_permissions`) have no `tenant_id`.
- Impact: global identity tables do not match strict tenant-column rule.

4. Tenant isolation in queries is not enforced for permission CRUD/list.
- Rule: `governance/AGENTS.md:97`.
- Evidence: `app/services/identity_service.py:267-314` and `app/api/routers/identity.py:274-337` are global, not tenant-scoped.
- Impact: one tenant admin with `identity.write` can mutate global permission catalog.

5. RBAC integration is bypassed for UI pages.
- Rule: `governance/AGENTS.md:98`.
- Evidence: UI endpoints only validate token (`app/api/routers/ui.py:21-30`) and do not call `require_perm(...)`.
- Impact: authenticated users can access UI views without page-level permission checks.

6. Critical export actions are not fully audited.
- Rule: `governance/AGENTS.md:99-106` (data export must be in audit log).
- Evidence: audit middleware logs only write methods (`app/infra/audit.py:13`, `app/infra/audit.py:43`), while export endpoints include GET exports (`app/api/routers/approval.py:48-53`, `app/api/routers/tenant_export.py:69-104`).
- Impact: export reads/downloads can bypass audit trail.

7. Business state changes missing events.
- Rule: `governance/AGENTS.md:121`.
- Evidence: `app/services/registry_service.py:107-112` (delete without event), `app/services/mission_service.py:166-173` (delete without event), `app/services/inspection_service.py:99-119` (template item create without event).
- Impact: event history is incomplete for state transitions.

## Potential Scalability Risks

1. Repeated full-table reads and Python-side aggregation.
- Evidence: `app/services/dashboard_service.py:25-42`, `app/services/reporting_service.py:31-43`, `app/services/reporting_service.py:55-72`, `app/services/defect_service.py:235-249`.
- Risk: latency and memory growth with data volume.

2. Dashboard WebSocket polling does heavy DB work every 2 seconds per client.
- Evidence: `app/api/routers/dashboard.py:86-105` + service methods above.
- Risk: linear load increase by active WS connections.

3. Permission collection does global scans then in-memory filtering.
- Evidence: `app/services/identity_service.py:388-396`.
- Risk: RBAC lookup cost grows with total roles/permissions.

4. Command dispatch waits for adapter ACK in request lifecycle.
- Evidence: `app/services/command_service.py:189-193`.
- Risk: long-running adapter calls consume API worker capacity.

5. Telemetry WebSocket hub is process-local memory.
- Evidence: `app/api/routers/telemetry.py:17-41`.
- Risk: no cross-instance fanout in multi-replica deployments.

6. Tenant export buffers full table data in memory before writing.
- Evidence: `app/services/tenant_export_service.py:135-144`, `app/services/tenant_export_service.py:157`.
- Risk: memory spikes for large tenant exports.

7. Redis telemetry state has no TTL strategy.
- Evidence: `app/services/telemetry_service.py:29`.
- Risk: unbounded key retention over time.

## Data Model Design Risks

1. Multiple tenant-owned relations still use single-column FKs.
- Evidence:
- `app/domain/models.py:159` (`drone_credentials.drone_id -> drones.id`)
- `app/domain/models.py:215` (`approvals.mission_id -> missions.id`)
- `app/domain/models.py:309` (`command_requests.drone_id -> drones.id`)
- `app/domain/models.py:671` (`inspection_tasks.mission_id -> missions.id`)
- `app/domain/models.py:683-684` (`inspection_observations.task_id/drone_id` single-column FK)
- `app/domain/models.py:702` (`inspection_exports.task_id -> inspection_tasks.id`)
- `app/domain/models.py:718` (`defects.observation_id -> inspection_observations.id`)
- Risk: DB allows cross-tenant reference shapes unless service checks always block them.

2. Identity relationship model is partially global.
- Evidence: `app/domain/models.py:121-126` (`role_permissions` has no `tenant_id`).
- Risk: permission binding model can create cross-tenant side effects.

3. Missing uniqueness for key domain invariants.
- Evidence: `app/domain/models.py:718` (`defects.observation_id` indexed but not unique), `app/domain/models.py:646` (`inspection_template_items.code` not unique per template).
- Risk: duplicates possible under concurrent writes.

4. Geospatial values are untyped strings.
- Evidence: `app/domain/models.py:672` (`area_geom`), `app/domain/models.py:765` (`location_geom`).
- Risk: weak validation and limited geospatial query guarantees.

5. Core domain fields are schema-flexible JSON blobs.
- Evidence: `app/domain/models.py:146-149`, `app/domain/models.py:196-203`, `app/domain/models.py:311-314`, `app/domain/models.py:353-356`.
- Risk: schema drift and difficult indexed analytics.

## Permission Model Weaknesses

1. Password hashing uses static-salt SHA-256 (no adaptive KDF).
- Evidence: `app/services/identity_service.py:50-52`.
- Risk: weak offline cracking resistance.

2. JWT has insecure default secret fallback.
- Evidence: `app/infra/auth.py:9`.
- Risk: token forgery in misconfigured environments.

3. Authorization is token-embedded permission snapshot.
- Evidence: `app/infra/auth.py:23-30`, `app/api/deps.py:36`.
- Risk: permission revocation takes effect only after token expiry.

4. UI authorization checks token validity/tenant only, not route permissions.
- Evidence: `app/api/routers/ui.py:21-30`, `app/api/routers/ui.py:39-113`.
- Risk: privilege separation is weaker on UI endpoints.

5. Token accepted in query string for UI/WS.
- Evidence: `app/api/routers/ui.py:34`, `app/api/routers/telemetry.py:94`, `app/api/routers/dashboard.py:65`.
- Risk: higher leakage surface in logs/history/proxies.

6. Tenant creation and bootstrap-admin are unauthenticated endpoints.
- Evidence: `app/api/routers/identity.py:50-58`, `app/api/routers/identity.py:117-125`.
- Risk: unsafe if exposed beyond controlled bootstrap contexts.

## Missing Test Coverage Areas

Current test inventory: 13 files, 34 `test_*` functions (`tests/`).

1. No dedicated tests for dashboard API/WS routes.
- Evidence: no `tests/test_dashboard.py`; WS logic exists in `app/api/routers/dashboard.py:64-109`.

2. No dedicated tests for reporting endpoints and report export.
- Evidence: no `tests/test_reporting.py`; endpoints in `app/api/routers/reporting.py:28-64`.

3. No dedicated tests for approval/compliance routes and audit export behavior.
- Evidence: no `tests/test_approval.py`; export endpoint in `app/api/routers/approval.py:48-53`.

4. No tests for UI routes and their auth behavior.
- Evidence: no `tests/test_ui.py`; routes in `app/api/routers/ui.py:33-113`.

5. No tests asserting audit middleware guarantees for critical export reads.
- Evidence: `app/infra/audit.py:43-46` excludes GET, but no tests verify required export audit coverage.

6. WebSocket negative-path auth cases are untested.
- Evidence: only happy-path WS test in `tests/test_telemetry.py:114-131`; no invalid/expired token WS tests.

7. Event completeness on delete operations is untested.
- Evidence: registry events tested for create/update only (`tests/test_registry.py:113-140`), no delete event tests.

## Dangerous Technical Debt

1. Governance execution metadata is inconsistent (`state` vs `progress`).
- Evidence: `phases/state.md:3-8` vs `logs/PROGRESS.md:13-14`.
- Risk: automation can resume from stale/incorrect phase checkpoints.

2. `run_all_phases.sh` performs broad host-side auto-commit/tag operations.
- Evidence: `infra/scripts/run_all_phases.sh:136-139`, `infra/scripts/run_all_phases.sh:147-153`.
- Risk: accidental commits of unrelated files and weak review boundaries.

3. Test suite has repeated tenant/bootstrap/login helper scaffolding.
- Evidence: repeated helpers across `tests/test_identity.py`, `tests/test_mission.py`, `tests/test_registry.py`, `tests/test_command.py`, `tests/test_alert.py`, `tests/test_telemetry.py`, `tests/test_tenant_export.py`.
- Risk: fixture drift and slower maintenance.

4. Event publish is not transactionally coupled with domain write commit.
- Evidence: e.g., `app/services/registry_service.py:49-55`, `app/services/mission_service.py:106-113`, `app/services/inspection_service.py:80-83`.
- Risk: write success with event loss on publish failure.

5. Report/export generation is custom and local-disk based.
- Evidence: `app/services/inspection_service.py:229-237`, `app/services/reporting_service.py:77-89`, `app/services/compliance_service.py:66-82`.
- Risk: operational fragility in multi-instance environments and harder long-term format evolution.

6. Containerization rule is partially bypassed by host-oriented scripting.
- Evidence: `governance/AGENTS.md:42-44` vs host commands in `infra/scripts/run_all_phases.sh:118`, `infra/scripts/run_all_phases.sh:137-139`.
- Risk: environment parity and reproducibility drift.

## Priority Remediation Order

1. Harden auth and permission model (KDF, JWT secret policy, UI RBAC parity, query-token removal).
2. Complete tenant-boundary DB constraints for remaining single-column FK paths.
3. Reconcile governance checkpoint/reporting consistency (`phases/state.md`, `logs/PROGRESS.md`, missing reports).
4. Add missing tests for dashboard/reporting/approval/ui/audit and WS negative paths.
5. Move high-cost aggregations and export flows toward scalable patterns (DB-side aggregates, async/export pipeline, shared artifact store).

