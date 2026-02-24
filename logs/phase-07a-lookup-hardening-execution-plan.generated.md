# PHASE 07A - Lookup Hardening Execution Plan

## Input Baseline
- Source analysis: `phases/phase-07a-lookup-hardening-analysis.md`
- Scope used for planning: `MEDIUM` findings only (`35` total)
- Target outcome: replace unscoped `session.get(...)` on tenant-scoped models with tenant-scoped query lookups while preserving behavior

## Batch Allocation Summary
| Batch | Theme | MEDIUM Findings | Services |
|---|---|---:|---|
| C1 | inspection + defect | 15 | `app/services/inspection_service.py`, `app/services/defect_service.py` |
| C2 | incident + alert | 4 | `app/services/incident_service.py`, `app/services/alert_service.py` |
| C3 | command | 3 | `app/services/command_service.py` |
| C4 | identity hardening | 13 | `app/services/identity_service.py` |

## Batch C1: Inspection + Defect
### Affected Services
- `app/services/inspection_service.py`
- `app/services/defect_service.py`

### Affected Models
- `InspectionTemplate`
- `InspectionTask`
- `InspectionObservation`
- `InspectionExport`
- `Defect`

### Findings Covered
- Inspection: rows `#8-#16` from analysis.
- Defect: rows `#2-#7` from analysis.

### Estimated Test Impact
- Current direct automated coverage appears absent for inspection/defect flows in `tests/`.
- Expected impact level: `HIGH` (new tests required, not just updates).
- Suggested minimum additions:
  - `4-6` tests for inspection lookup endpoints/service methods (tenant hit, cross-tenant miss, not-found parity).
  - `3-4` tests for defect lookup paths (including observation/task chained lookups).

### Migration Impact
- `None` required for correctness.
- No schema changes expected; lookup hardening is query-layer only.

### Safe Refactor Pattern
- Replace:
  - `obj = session.get(Model, model_id)`
  - `if obj is None or obj.tenant_id != tenant_id: raise NotFoundError(...)`
- With:
  - `obj = session.exec(select(Model).where(Model.tenant_id == tenant_id).where(Model.id == model_id)).first()`
  - `if obj is None: raise NotFoundError(...)`
- Keep existing error messages and exception types unchanged.
- Prefer local helpers per service (for example `_get_scoped_task`, `_get_scoped_template`) to reduce divergence.

### Rollback Safety
- Land as an isolated PR/commit for C1 only.
- Run targeted tests plus smoke API checks before merge.
- If regression occurs, revert the C1 commit directly; no DB rollback needed.

## Batch C2: Incident + Alert
### Affected Services
- `app/services/incident_service.py`
- `app/services/alert_service.py`

### Affected Models
- `Incident`
- `AlertRecord`

### Findings Covered
- Incident: row `#17`.
- Alert: rows `#49-#51`.

### Estimated Test Impact
- Alert has existing tests in `tests/test_alert.py` (`2` tests) likely to remain mostly stable with tenant-scoped retrieval.
- Incident appears to have no direct test file; add targeted coverage.
- Expected impact level: `MEDIUM`.
- Suggested minimum additions/updates:
  - Add `2-3` incident tests (tenant hit/miss and lifecycle path).
  - Add `1` alert cross-tenant negative test for get/ack/close path.

### Migration Impact
- `None`.
- No schema/index change required for functional rollout.

### Safe Refactor Pattern
- Apply the same scoped-by-tenant-by-id retrieval pattern to `Incident` and `AlertRecord`.
- Keep state transition logic untouched; change only lookup lines.
- Preserve `NotFoundError` and `ConflictError` semantics exactly.

### Rollback Safety
- Release C2 separately from C1/C3/C4.
- Validate with `tests/test_alert.py` and new incident tests.
- Revert C2 commit if needed; no migration rollback path needed.

## Batch C3: Command
### Affected Services
- `app/services/command_service.py`

### Affected Models
- `CommandRequestRecord`
- `Drone`

### Findings Covered
- Rows `#18-#20`.

### Estimated Test Impact
- Existing command coverage in `tests/test_command.py` (`3` tests) directly exercises these paths.
- Expected impact level: `LOW-MEDIUM`.
- Suggested additions:
  - `1` explicit cross-tenant retrieval negative test for command query/update path.

### Migration Impact
- `None`.
- Existing indexes (`tenant_id`, idempotency uniqueness by tenant) remain sufficient for this hardening change.

### Safe Refactor Pattern
- For both command record and drone retrieval:
  - move from `session.get(...)` + post-check to scoped `select(... tenant_id ... id ...)`.
- Keep idempotency and ack persistence flow unchanged.
- Ensure transaction boundaries and commit timing remain identical.

### Rollback Safety
- Deploy as a stand-alone batch with existing command tests as gate.
- On regression, single-commit revert restores prior behavior quickly.
- No database rollback action required.

## Batch C4: Identity Hardening
### Affected Services
- `app/services/identity_service.py`

### Affected Models
- `User`
- `Role`

### Findings Covered
- Rows `#27-#32`, `#36-#37`, `#39-#40`, `#42`, `#45`, `#48`.

### Estimated Test Impact
- Existing identity coverage in `tests/test_identity.py` (`4` tests) intersects these flows.
- Expected impact level: `MEDIUM-HIGH` because user/role binding flows are central.
- Suggested additions/updates:
  - `2-3` tests for user lookup/update/delete tenant scoping.
  - `2-3` tests for role lookup/update/delete and bind/unbind paths.

### Migration Impact
- `None`.
- Identity hardening in this batch is query-level only.

### Safe Refactor Pattern
- Introduce scoped helpers in identity service (for example `_get_scoped_user`, `_get_scoped_role`).
- Replace repeated `session.get(User|Role, id)` usages with helper-backed tenant-scoped selects.
- Keep global model behavior unchanged (`Tenant`, `Permission`, and existing composite-link logic not in MEDIUM scope).

### Rollback Safety
- Merge C4 independently after C1-C3 stabilization.
- Gate with full identity test suite and cross-tenant regression tests.
- Revert C4 commit if needed; no migration rollback required.

## Cross-Batch Execution Order
1. `C3` (smallest blast radius, strong existing tests)
2. `C2` (moderate scope, partial existing tests)
3. `C4` (auth/authorization sensitive)
4. `C1` (largest untested surface; pair with new tests before merge)

## Global Guardrails
- Keep each batch in a separate commit/PR for clean rollback.
- Do not change API contracts, status codes, or error text.
- Keep refactor mechanical: lookup hardening only, no business-rule changes.
- Require tenant isolation regression tests in each batch before merge.
