# Phase 07B DB Boundary Master Blueprint

## 0) Basis
- Source blueprint: `phases/phase-07-master-blueprint.md`
- Boundary inventory: `governance/tenant_boundary_matrix.md`

## 1) Goal
Complete DB-level tenant boundary enforcement for all remaining tenant-owned tables, with service lookup behavior aligned to tenant-scoped access patterns established in 07A.

## 2) Definition of Done
- Every tenant-owned table has `UNIQUE (tenant_id, id)` (or composite PK includes `tenant_id`).
- Every FK between tenant-owned tables is composite and includes `tenant_id` with `ON DELETE RESTRICT`.
- All service lookups touching these tables are tenant-scoped (07A provides baseline).
- Alembic uses 3-step migration strategy (expand -> backfill/validate -> enforce) per batch.
- Tests include at least one DB-level composite FK enforcement check per batch.

## 3) Execution Order (Least Coupled -> Most Coupled)
1. `B1`: inspection domain tables (`templates/tasks/exports/observations`, including template items as needed)
2. `B2`: defect domain tables
3. `B3`: incident/alert persistence tables (if constraints still missing)
4. `B4`: command tables (if constraints still missing)
5. `B5`: reporting/export tables

## 4) Batch Playbooks

### B1: Inspection Domain
- Scope tables:
  - `inspection_templates`
  - `inspection_template_items`
  - `inspection_tasks`
  - `inspection_observations`
  - `inspection_exports` (if tenant-parent FK hardening is still required)
- Scope code files allowed to modify:
  - `app/domain/models.py` (inspection-model definitions only)
  - `app/services/inspection_service.py`
  - `infra/migrations/versions/*phase07b_b1_inspection_*.py`
  - `tests/test_inspection.py` (or dedicated inspection boundary test file)
- Migration filenames pattern:
  - `*_phase07b_b1_inspection_expand.py`
  - `*_phase07b_b1_inspection_backfill_validate.py`
  - `*_phase07b_b1_inspection_enforce.py`
- Required validations:
  - `ruff check app tests infra/scripts`
  - `mypy app`
  - `pytest` (must include at least one DB-level cross-tenant composite FK rejection for B1)
  - `alembic upgrade head`
- Required grep checks:
  - `rg -n "session\\.get\\(" app/services/inspection_service.py`
  - `rg -n "select\\(Inspection|where\\(.*\\.id\\s*==" app/services/inspection_service.py`

### B2: Defect Domain
- Scope tables:
  - `defects`
  - `defect_actions`
- Scope code files allowed to modify:
  - `app/domain/models.py` (defect-model definitions only)
  - `app/services/defect_service.py`
  - `infra/migrations/versions/*phase07b_b2_defect_*.py`
  - `tests/test_defect.py` (or dedicated defect boundary test file)
- Migration filenames pattern:
  - `*_phase07b_b2_defect_expand.py`
  - `*_phase07b_b2_defect_backfill_validate.py`
  - `*_phase07b_b2_defect_enforce.py`
- Required validations:
  - `ruff check app tests infra/scripts`
  - `mypy app`
  - `pytest` (must include at least one DB-level cross-tenant composite FK rejection for B2)
  - `alembic upgrade head`
- Required grep checks:
  - `rg -n "session\\.get\\(" app/services/defect_service.py`
  - `rg -n "select\\(Defect|where\\(.*\\.id\\s*==" app/services/defect_service.py`

### B3: Incident + Alert Persistence
- Scope tables:
  - `incidents`
  - `alerts`
- Scope code files allowed to modify:
  - `app/domain/models.py` (incident/alert model definitions only)
  - `app/services/incident_service.py`
  - `app/services/alert_service.py`
  - `infra/migrations/versions/*phase07b_b3_incident_alert_*.py`
  - `tests/test_incident.py`
  - `tests/test_alert.py`
- Migration filenames pattern:
  - `*_phase07b_b3_incident_alert_expand.py`
  - `*_phase07b_b3_incident_alert_backfill_validate.py`
  - `*_phase07b_b3_incident_alert_enforce.py`
- Required validations:
  - `ruff check app tests infra/scripts`
  - `mypy app`
  - `pytest` (must include at least one DB-level cross-tenant composite FK rejection for B3)
  - `alembic upgrade head`
- Required grep checks:
  - `rg -n "session\\.get\\(" app/services/incident_service.py app/services/alert_service.py`
  - `rg -n "where\\(.*\\.id\\s*==" app/services/incident_service.py app/services/alert_service.py`

### B4: Command Persistence
- Scope tables:
  - `command_requests`
- Scope code files allowed to modify:
  - `app/domain/models.py` (command model definitions only)
  - `app/services/command_service.py`
  - `infra/migrations/versions/*phase07b_b4_command_*.py`
  - `tests/test_command.py`
- Migration filenames pattern:
  - `*_phase07b_b4_command_expand.py`
  - `*_phase07b_b4_command_backfill_validate.py`
  - `*_phase07b_b4_command_enforce.py`
- Required validations:
  - `ruff check app tests infra/scripts`
  - `mypy app`
  - `pytest` (must include at least one DB-level cross-tenant composite FK rejection for B4)
  - `alembic upgrade head`
- Required grep checks:
  - `rg -n "session\\.get\\(" app/services/command_service.py`
  - `rg -n "where\\(.*\\.id\\s*==" app/services/command_service.py`

### B5: Reporting / Export Persistence
- Scope tables:
  - `approval_records`
  - any remaining reporting/export persistence tables not fully covered by B1-B4
- Scope code files allowed to modify:
  - `app/domain/models.py` (reporting/compliance model definitions only)
  - `app/services/reporting_service.py`
  - `app/services/compliance_service.py`
  - `infra/migrations/versions/*phase07b_b5_reporting_export_*.py`
  - `tests/test_reporting.py`
  - `tests/test_compliance.py`
- Migration filenames pattern:
  - `*_phase07b_b5_reporting_export_expand.py`
  - `*_phase07b_b5_reporting_export_backfill_validate.py`
  - `*_phase07b_b5_reporting_export_enforce.py`
- Required validations:
  - `ruff check app tests infra/scripts`
  - `mypy app`
  - `pytest` (must include at least one DB-level cross-tenant composite FK rejection for B5)
  - `alembic upgrade head`
- Required grep checks:
  - `rg -n "session\\.get\\(" app/services/reporting_service.py app/services/compliance_service.py`
  - `rg -n "where\\(.*\\.id\\s*==" app/services/reporting_service.py app/services/compliance_service.py`

## 5) Safety Rules
- Strictly batch-scoped changes only; never cross-domain edits.
- One batch per PR/commit set; no mixed-domain migrations in the same batch.
- Only files listed in the active batch scope may be edited.
- If an out-of-scope dependency is discovered, stop and open a follow-up batch instead of expanding scope.
- Preserve existing API semantics (`404` cross-tenant behavior) while hardening DB constraints.
