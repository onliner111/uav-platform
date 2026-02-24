# Phase 07A Lookup Hardening Execution Plan

## Scope
- Source of truth: `phases/phase-07a-lookup-hardening-analysis.md`
- Included findings: `MEDIUM` only
- Change type: lookup hardening only (no schema or business-rule changes)

## Batch Mapping From MEDIUM Findings
- `C1`: `inspection_service` + `defect_service`
- `C2`: `incident_service` + `alert_service`
- `C3`: `command_service`
- `C4`: `identity_service` (`User`/`Role` tenant-scoped lookups only)

## Batch C1 (inspection + defect)
- Affected services: `app/services/inspection_service.py`, `app/services/defect_service.py`
- Affected models: `InspectionTemplate`, `InspectionTask`, `InspectionExport`, `InspectionObservation`, `Defect`
- Number of lookup changes: `15` (`inspection_service: 9`, `defect_service: 6`)
- Test impact: high (largest count, two services, multiple model relationships)
- E2E impact: medium-high (inspection/defect retrieval and chained flows can change 404 paths)
- Migration impact: none
- Rollback safety plan:
  - isolate as a dedicated commit/PR for C1 only
  - keep old/new behavior parity on error message and status code
  - if regression appears, revert C1 commit (no DB rollback required)
- Estimated change complexity: high

## Batch C2 (incident + alert)
- Affected services: `app/services/incident_service.py`, `app/services/alert_service.py`
- Affected models: `Incident`, `AlertRecord`
- Number of lookup changes: `4` (`incident_service: 1`, `alert_service: 3`)
- Test impact: medium
- E2E impact: medium (incident task creation and alert lifecycle endpoints)
- Migration impact: none
- Rollback safety plan:
  - ship C2 independently from C1/C3/C4
  - verify incident and alert lifecycle behavior
  - revert C2 commit if needed (no DB rollback required)
- Estimated change complexity: medium

## Batch C3 (command)
- Affected services: `app/services/command_service.py`
- Affected models: `CommandRequestRecord`, `Drone`
- Number of lookup changes: `3`
- Test impact: low-medium
- E2E impact: medium (command dispatch, command query, ack/timeout flows)
- Migration impact: none
- Rollback safety plan:
  - release C3 as a single isolated change set
  - validate command happy-path and cross-tenant 404 behavior
  - revert C3 commit if needed (no DB rollback required)
- Estimated change complexity: low

## Batch C4 (identity hardening: user/role only)
- Affected services: `app/services/identity_service.py`
- Affected models: `User`, `Role`
- Number of lookup changes: `13`
- Test impact: high (authz-critical service and many call sites)
- E2E impact: medium-high (user/role CRUD and binding/unbinding paths)
- Migration impact: none
- Rollback safety plan:
  - keep C4 separate from all other batches
  - enforce strict 404 parity for tenant isolation behavior
  - revert C4 commit if needed (no DB rollback required)
- Estimated change complexity: high

## Safe Implementation Pattern
- Introduce private tenant-scoped helper methods in each service:
  - examples: `_get_scoped_user`, `_get_scoped_role`, `_get_scoped_task`, `_get_scoped_alert`
- Replace `session.get(Model, id)` with scoped select:
  - `session.exec(select(Model).where(Model.tenant_id == tenant_id).where(Model.id == model_id)).first()`
- Enforce consistent 404 behavior:
  - if scoped lookup returns `None`, raise the existing `NotFoundError` path
  - preserve current error text/status semantics

## Validation Checklist Before Commit
- `ruff`:
  - run: `ruff check .`
- `mypy`:
  - run: `mypy app`
- `pytest`:
  - run: `pytest`
- `e2e`:
  - run project e2e suite command used by this repo/CI
- grep for remaining `session.get` in service layer:
  - run: `rg -n "session\\.get\\(" app/services`
  - confirm only intentionally retained non-tenant/global/composite lookups remain

## Sequencing Recommendation
1. C1 (inspection + defect)
2. C2 (incident + alert)
3. C3 (command)
4. C4 (identity)

Justification:
- C1 has the highest structural depth (most interconnected tenant-scoped lookups), so it should be addressed first to de-risk downstream batches.
- C4 is auth-critical, so it should run last after lower-risk service hardening is validated.
