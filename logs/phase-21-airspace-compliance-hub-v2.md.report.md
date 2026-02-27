# Phase Report

- Phase: `phase-21-airspace-compliance-hub-v2.md`
- Status: `SUCCESS`
- Completed at (UTC): `2026-02-27T16:35:00Z`

## What Was Delivered
- Implemented layered airspace policy controls with fixed precedence:
  - `policy_layer`: `PLATFORM_DEFAULT | TENANT | ORG_UNIT`
  - `policy_effect`: `ALLOW | DENY`
  - `org_unit_id` scoped override support for org-level policy
- Integrated hierarchical policy resolver into compliance gates:
  - mission plan validation (`mission create/update`)
  - command precheck (`GOTO` and `START_MISSION` guardrails)
- Added configurable approval flow minimal chain:
  - approval flow template API
  - approval flow instance API
  - approve/reject/rollback action API
  - mission compatibility by driving mission state to `APPROVED/REJECTED` on terminal action
- Enhanced preflight checklist with template version and evidence requirements:
  - `template_version`
  - `evidence_requirements`
  - item-level evidence input and required-evidence enforcement
- Added compliance decision evidence chain:
  - decision record model/API/export (`ALLOW/DENY/APPROVE/REJECT`)
  - records for mission-plan validation, command precheck, preflight run gate, and approval flow decisions
- Added task-center linkage:
  - mission-linked task creation writes `context_data.compliance_snapshot`
- Added migration chain:
  - `202602270083_phase21_compliance_hub_v2_expand.py`
  - `202602270084_phase21_compliance_hub_v2_backfill_validate.py`
  - `202602270085_phase21_compliance_hub_v2_enforce.py`
- Added phase demo:
  - `infra/scripts/demo_phase21_airspace_compliance_hub_v2.py`

## How To Verify
- `docker compose -f infra/docker-compose.yml run --rm --build app ruff check app tests infra/scripts`
- `docker compose -f infra/docker-compose.yml run --rm --build app mypy app`
- `docker compose -f infra/docker-compose.yml run --rm --build app pytest -q`
- `docker compose -f infra/docker-compose.yml up --build -d`
- `docker compose -f infra/docker-compose.yml run --rm --build app alembic upgrade head`
- `docker compose -f infra/docker-compose.yml run --rm --build app-tools python -m app.infra.openapi_export`
- `docker compose -f infra/docker-compose.yml run --rm --build -e APP_BASE_URL=http://app:8000 app-tools python infra/scripts/demo_e2e.py`
- `docker compose -f infra/docker-compose.yml run --rm --build -e APP_BASE_URL=http://app:8000 app-tools python infra/scripts/verify_smoke.py`
- `docker compose -f infra/docker-compose.yml run --rm --build -e APP_BASE_URL=http://app:8000 app-tools python infra/scripts/demo_phase21_airspace_compliance_hub_v2.py`

## Key Files Changed
- `app/domain/models.py`
- `app/services/compliance_service.py`
- `app/api/routers/compliance.py`
- `app/services/mission_service.py`
- `app/services/command_service.py`
- `app/services/task_center_service.py`
- `tests/test_compliance.py`
- `tests/test_task_center.py`
- `infra/scripts/demo_phase21_airspace_compliance_hub_v2.py`
- `infra/migrations/versions/202602270083_phase21_compliance_hub_v2_expand.py`
- `infra/migrations/versions/202602270084_phase21_compliance_hub_v2_backfill_validate.py`
- `infra/migrations/versions/202602270085_phase21_compliance_hub_v2_enforce.py`
