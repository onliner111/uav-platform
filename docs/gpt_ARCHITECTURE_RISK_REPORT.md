# GPT Architecture Risk Report

Date: 2026-02-22  
Scope: `app/`, `tests/`, `infra/scripts/`, `Makefile`, compose files, and AGENTS governance alignment.

## 1) Tight Coupling Areas

1. Telemetry ingestion is tightly coupled to alert generation.
   - Evidence: `app/services/telemetry_service.py:19`, `app/services/telemetry_service.py:35`
   - Risk: Telemetry path latency and failure domain are coupled to alert logic. Any alert-rule slowdown affects ingest throughput.

2. Command execution is tightly coupled to concrete adapter implementations.
   - Evidence: `app/services/command_service.py:12`, `app/services/command_service.py:13`, `app/services/command_service.py:14`, `app/services/command_service.py:55`
   - Risk: Extending/altering adapter behavior requires service-level edits; plugin boundary is partially bypassed.

3. UI router bypasses standard dependency-based auth/RBAC flow.
   - Evidence: `app/api/routers/ui.py:11`, `app/api/routers/ui.py:21`, `app/api/routers/ui.py:42`, `app/api/routers/ui.py:85`, `app/api/routers/ui.py:108`
   - Risk: Permission enforcement becomes inconsistent between UI and API routes, increasing maintenance and security drift.

4. Event infrastructure is global singleton + global DB engine.
   - Evidence: `app/infra/events.py:15`, `app/infra/events.py:29`, `app/infra/events.py:57`
   - Risk: Hard to isolate, shard, or replace event infrastructure; limits scale-out patterns.

5. Domain persistence models and API schemas are highly coupled in one large file.
   - Evidence: `app/domain/models.py` (901 lines)
   - Risk: High change blast radius and frequent merge conflicts; harder to evolve schema independently from API DTOs.

## 2) Violations of governance/AGENTS.md Rules

1. Government Mode tenant requirement conflict: some tables do not include `tenant_id`.
   - Evidence: `app/domain/models.py:83` (`Permission`), `app/domain/models.py:92` (`UserRole`), `app/domain/models.py:100` (`RolePermission`)
   - Rule impact: Conflicts with "All new tables MUST include tenant_id" if applied strictly platform-wide.

2. Tenant isolation weakness for permission management (global CRUD across tenants).
   - Evidence: `app/api/routers/identity.py:280`, `app/api/routers/identity.py:294`, `app/api/routers/identity.py:304`, `app/api/routers/identity.py:318`, `app/api/routers/identity.py:332`, `app/services/identity_service.py:259`, `app/services/identity_service.py:300`
   - Rule impact: `Permission` is global, and mutation is not tenant-scoped.

3. Critical data export action may not be audited.
   - Evidence: `app/api/routers/approval.py:49`, `app/infra/audit.py:13`, `app/infra/audit.py:43`
   - Rule impact: `GET /api/approvals/audit-export` performs export, but audit middleware only logs write methods.

4. Business state changes without corresponding domain events.
   - Evidence:
     - `app/services/registry_service.py:103` (`delete_drone`, no publish after delete)
     - `app/services/mission_service.py:153` (`delete_mission`, no publish after delete)
     - `app/services/inspection_service.py:71` (`create_template_item`, no event)
   - Rule impact: Conflicts with strict "Business state changes MUST generate events."

5. Containerization discipline inconsistencies in automation scripts/tooling.
   - Evidence: `Makefile:38`, `Makefile:39`, `infra/scripts/run_all_phases.sh:118`, `infra/scripts/run_all_phases.sh:137`
   - Rule impact: Some operational steps run host commands directly (filesystem ops, `codex`, `git`) instead of compose-contained execution.

## 3) Potential Scalability Risks

1. Repeated full-table scans and in-memory counting/filtering.
   - Evidence:
     - `app/services/dashboard_service.py:25`, `app/services/dashboard_service.py:26`, `app/services/dashboard_service.py:27`, `app/services/dashboard_service.py:48`
     - `app/services/reporting_service.py:31`, `app/services/reporting_service.py:32`, `app/services/reporting_service.py:33`, `app/services/reporting_service.py:55`, `app/services/reporting_service.py:56`, `app/services/reporting_service.py:57`
   - Risk: O(N) per request; poor latency and DB pressure at scale.

2. Permission collection loads global tables then filters in Python.
   - Evidence: `app/services/identity_service.py:365`, `app/services/identity_service.py:371`, `app/services/identity_service.py:377`
   - Risk: Degrades rapidly with tenant/user growth.

3. Mission run transitions load all runs before filtering.
   - Evidence: `app/services/mission_service.py:250`, `app/services/mission_service.py:254`
   - Risk: Inefficient state transition path under high mission-run volume.

4. WebSocket fanout state is in-process memory only.
   - Evidence: `app/api/routers/telemetry.py:19`, `app/api/routers/dashboard.py:84`
   - Risk: Multi-instance deployments lose consistent subscriber state; no cross-instance broadcast.

5. Synchronous audit writes in request path.
   - Evidence: `app/infra/audit.py:16`, `app/infra/audit.py:52`
   - Risk: Adds write latency to all mutating API calls.

6. Redis telemetry state has no TTL/eviction strategy in service logic.
   - Evidence: `app/services/telemetry_service.py:29`
   - Risk: Unbounded key growth by tenant+drone.

7. Export artifacts are written to local filesystem.
   - Evidence: `app/services/inspection_service.py:215`, `app/services/compliance_service.py:68`, `app/services/reporting_service.py:79`
   - Risk: Not horizontally robust; artifacts may disappear or diverge across replicas.

## 4) Data Model Design Risks

1. Cross-tenant join tables lack explicit tenancy columns.
   - Evidence: `app/domain/models.py:92`, `app/domain/models.py:100`
   - Risk: Tenant boundary relies on application logic and indirect joins.

2. Missing DB-level uniqueness for key business invariants.
   - Evidence:
     - `Defect.observation_id` has no unique constraint: `app/domain/models.py:642`
     - App-level dedupe only: `app/services/defect_service.py:62`
     - `InspectionTemplateItem.code` not unique within template: `app/domain/models.py:586`
   - Risk: Race conditions can produce duplicate records.

3. Service-level referential checks are incomplete for tenant isolation.
   - Evidence:
     - Mission accepts arbitrary `drone_id` without tenant validation: `app/services/mission_service.py:81`, `app/services/mission_service.py:132`
     - Inspection task accepts arbitrary `mission_id` without tenant validation: `app/services/inspection_service.py:116`
   - Risk: Cross-tenant references can be created if IDs are known.

4. Geospatial fields are plain strings, not typed/geospatial constrained.
   - Evidence: `app/domain/models.py:602`, `app/domain/models.py:670`
   - Risk: Weak validation and limited spatial query performance/correctness.

5. Heavy use of flexible JSON for core business data.
   - Evidence: `app/domain/models.py:162`, `app/domain/models.py:166`, `app/domain/models.py:122`
   - Risk: Schema drift, weak validation, and poor indexability.

## 5) Permission Model Weaknesses

1. Password hashing is SHA-256 with static salt (not a password KDF).
   - Evidence: `app/services/identity_service.py:51`, `app/services/identity_service.py:52`
   - Risk: Weak resistance to offline cracking.

2. JWT secret has insecure default fallback.
   - Evidence: `app/infra/auth.py:9`
   - Risk: Misconfigured environments are vulnerable to token forgery.

3. Authorization decisions depend on permission snapshot inside JWT.
   - Evidence: `app/infra/auth.py:14`, `app/infra/auth.py:22`, `app/api/deps.py:32`
   - Risk: Role/permission revocations do not take effect until token expiry.

4. Token-only UI access lacks route-level RBAC checks.
   - Evidence: `app/api/routers/ui.py:21`, `app/api/routers/ui.py:39`, `app/api/routers/ui.py:82`, `app/api/routers/ui.py:94`, `app/api/routers/ui.py:105`
   - Risk: Any authenticated token can access multiple operational UI pages regardless of explicit permissions.

5. Token in query string for WebSocket/UI flows.
   - Evidence: `app/api/routers/telemetry.py:94`, `app/api/routers/dashboard.py:65`, `app/api/routers/ui.py:33`
   - Risk: Token leakage via logs, browser history, proxies, and monitoring tools.

6. Tenant/bootstrap endpoints are unauthenticated by design.
   - Evidence: `app/api/routers/identity.py:50`, `app/api/routers/identity.py:118`
   - Risk: Operationally dangerous outside controlled environments.

## 6) Missing Test Coverage Areas

Current automated test files: 9 total in `tests/`, focused on health, identity, registry, mission, command, telemetry, alert, adapters, event bus.

Coverage gaps:

1. No direct test modules for inspection, defect, incident, dashboard, approval/compliance, reporting, or UI routers.
   - Evidence: missing files such as `tests/test_inspection.py`, `tests/test_defect.py`, `tests/test_incident.py`, `tests/test_dashboard.py`, `tests/test_approval.py`, `tests/test_reporting.py`, `tests/test_ui.py`

2. No automated assertions for critical audit-log guarantees (especially export auditing).
   - Evidence: search in tests only finds `/readyz` checks (`tests/test_health.py:15`, `tests/test_health.py:19`); no `AuditLog` assertions.

3. No negative-path tests for WebSocket auth failures and token misuse.
   - Evidence: existing WS tests are happy-path only (`tests/test_telemetry.py:115` onward).

4. No tests validating cross-tenant safety of global permission CRUD.
   - Evidence: permission endpoints exist (`app/api/routers/identity.py:275` onward), but no dedicated tests target cross-tenant mutation controls.

5. No tests for state-change event completeness on delete/other transitions.
   - Evidence: event tests cover create/update flows (e.g., registry/mission/alert/command), not delete flows.

## 7) Dangerous Technical Debt

1. Oversized unified model file (`app/domain/models.py`, 901 lines) mixing ORM entities and API DTOs.
   - Impact: maintainability, onboarding cost, higher defect probability during schema changes.

2. Duplicate compose definitions (`docker-compose.yml` and `infra/docker-compose.yml`).
   - Impact: config drift risk and operational confusion.

3. Repeated test scaffolding across many test files.
   - Evidence: duplicated helpers in `tests/test_identity.py:37`, `tests/test_command.py:42`, `tests/test_telemetry.py:56`, `tests/test_alert.py:57`, `tests/test_mission.py:38`, `tests/test_registry.py:38`
   - Impact: brittle updates and inconsistent fixture behavior.

4. Event emission is not transactional with business writes (commit first, publish after).
   - Evidence: patterns in `app/services/registry_service.py:47`, `app/services/mission_service.py:96`, `app/services/inspection_service.py:124`
   - Impact: write succeeds but event may be missing on publish failure.

5. HTML/PDF export generation is custom and directly writes unsanitized/inline content.
   - Evidence: `app/services/inspection_service.py:250`, `app/services/inspection_service.py:254`, `app/services/reporting_service.py:91`
   - Impact: content safety and long-term report-format maintainability risks.

## Priority Remediation Sequence

1. Fix high-risk auth/permission issues: strong password KDF, mandatory JWT secret, UI RBAC parity, token transport hardening.
2. Enforce tenant integrity in schema and service checks (`tenant_id` strategy, cross-tenant FK validation).
3. Close AGENTS compliance gaps for audit/event integrity (especially export audit and delete events).
4. Replace high-cost full scans with DB-side aggregates and pagination.
5. Introduce outbox/transactional event pattern and shared artifact storage for scale.
6. Add missing tests for currently uncovered modules and negative/security paths.

