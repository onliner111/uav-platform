Phase: phase-05-compliance.md
Status: SUCCESS

What was delivered
- Added `approval_records` model and compliance API (`POST/GET /api/approvals`) with tenant-scoped RBAC checks.
- Added audit export endpoint (`GET /api/approvals/audit-export`) and phase demo.

How to verify
- `docker --context default compose -f infra/docker-compose.yml run --rm --build -e APP_BASE_URL=http://app:8000 app-tools python infra/scripts/demo_compliance_phase5.py`

Demos
- Create approval via `POST /api/approvals`
- Export audit via `GET /api/approvals/audit-export`

Risks/Notes
- Audit export is JSON file output in `logs/exports/`.
- Approval schema intentionally lightweight for deterministic workflow integration.

Key files changed
- app/services/compliance_service.py
- app/api/routers/approval.py
- app/domain/models.py
- infra/scripts/demo_compliance_phase5.py
