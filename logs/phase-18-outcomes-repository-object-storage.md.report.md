# Phase Report

- Phase: `phase-18-outcomes-repository-object-storage.md`
- Status: `SUCCESS`

## What Was Delivered
- `18-WP1` object storage minimal loop: raw upload session init/upload/complete/download.
- `18-WP2` outcome version lineage + scoped write access hardening.
- `18-WP3` outcome report template center + report export jobs (PDF/Word).
- `18-WP4` report artifact retention lifecycle + explicit audit action linkage.
- `18-WP5` raw storage region + hot/warm/cold tier model and transition API.

## How To Verify
- `docker compose -f infra/docker-compose.yml run --rm app-tools ruff check app tests infra/scripts`
- `docker compose -f infra/docker-compose.yml run --rm app-tools mypy app`
- `docker compose -f infra/docker-compose.yml run --rm app-tools python -m pytest -q`
- `docker compose -f infra/docker-compose.yml up --build -d`
- `docker compose -f infra/docker-compose.yml run --rm app-tools alembic upgrade head`
- `docker compose -f infra/docker-compose.yml run --rm app-tools python -m app.infra.openapi_export`
- `docker compose -f infra/docker-compose.yml run --rm -e APP_BASE_URL=http://app:8000 app-tools python infra/scripts/demo_e2e.py`
- `docker compose -f infra/docker-compose.yml run --rm -e APP_BASE_URL=http://app:8000 app-tools python infra/scripts/verify_smoke.py`

## Demos
- Raw object upload/download:
  - `POST /api/outcomes/raw/uploads:init`
  - `PUT /api/outcomes/raw/uploads/{session_id}/content`
  - `POST /api/outcomes/raw/uploads/{session_id}:complete`
  - `GET /api/outcomes/raw/{raw_id}/download`
- Outcome version query:
  - `GET /api/outcomes/records/{outcome_id}/versions`
- Outcome report template/export/lifecycle:
  - `POST/GET /api/reporting/outcome-report-templates`
  - `POST/GET /api/reporting/outcome-report-exports*`
  - `POST /api/reporting/outcome-report-exports:retention`
- Raw storage tier transition:
  - `PATCH /api/outcomes/raw/{raw_id}/storage`

## Risks/Notes
- `WORD` export currently uses minimal `.docx` renderer for deterministic regression; complex styling is not yet implemented.
- Object storage backend remains `local` in this phase; cross-region behavior is modeled via metadata/tier transition APIs.

## Key Files Changed
- app/domain/models.py
- app/services/object_storage_service.py
- app/services/outcome_service.py
- app/services/reporting_service.py
- app/api/routers/outcomes.py
- app/api/routers/reporting.py
- tests/test_outcomes.py
- tests/test_reporting.py
- infra/migrations/versions/202602260071_phase18_wp1_object_storage_expand.py
- infra/migrations/versions/202602260072_phase18_wp1_object_storage_backfill_validate.py
- infra/migrations/versions/202602260073_phase18_wp1_object_storage_enforce.py
- infra/migrations/versions/202602260074_phase18_wp2_outcome_version_expand.py
- infra/migrations/versions/202602260075_phase18_wp2_outcome_version_backfill_validate.py
- infra/migrations/versions/202602260076_phase18_wp2_outcome_version_enforce.py
- infra/migrations/versions/202602260077_phase18_wp3_report_template_export_expand.py
- infra/migrations/versions/202602260078_phase18_wp3_report_template_export_backfill_validate.py
- infra/migrations/versions/202602260079_phase18_wp3_report_template_export_enforce.py
- infra/migrations/versions/202602260080_phase18_wp5_storage_tier_region_expand.py
- infra/migrations/versions/202602260081_phase18_wp5_storage_tier_region_backfill_validate.py
- infra/migrations/versions/202602260082_phase18_wp5_storage_tier_region_enforce.py
