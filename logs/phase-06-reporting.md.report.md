Phase: phase-06-reporting.md
Status: SUCCESS

What was delivered
- Added reporting APIs: overview, closure-rate, device-utilization, and export.
- Implemented report export file generation (`.pdf`) and phase demo validation.

How to verify
- `docker --context default compose -f infra/docker-compose.yml run --rm --build -e APP_BASE_URL=http://app:8000 app-tools python infra/scripts/demo_reporting_phase6.py`

Demos
- `GET /api/reporting/overview`
- `GET /api/reporting/closure-rate`
- `GET /api/reporting/device-utilization`
- `POST /api/reporting/export`

Risks/Notes
- PDF export uses a minimal deterministic generator (sufficient for acceptance/demo).
- Device utilization aggregates by mission-drone linkage and inspection mission mapping.

Key files changed
- app/services/reporting_service.py
- app/api/routers/reporting.py
- app/domain/models.py
- infra/scripts/demo_reporting_phase6.py
