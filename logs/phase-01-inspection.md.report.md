Phase: phase-01-inspection.md
Status: SUCCESS

What was delivered
- Added inspection data model and migration: templates, template items, tasks, observations, exports.
- Implemented inspection APIs, export endpoint, Jinja2 UI (`/ui/inspection`, `/ui/inspection/tasks/{task_id}`), Leaflet map rendering, and phase demo script.

How to verify
- `docker --context default compose -f infra/docker-compose.yml run --rm app alembic upgrade head`
- `docker --context default compose -f infra/docker-compose.yml run --rm --build -e APP_BASE_URL=http://app:8000 app-tools python infra/scripts/demo_inspection_phase1.py`

Demos
- Open `GET /ui/inspection?token=<jwt>`
- Open `GET /ui/inspection/tasks/{task_id}?token=<jwt>`
- Export via `POST /api/inspection/tasks/{task_id}/export?format=html`

Risks/Notes
- `area_geom` uses text storage for compatibility, not PostGIS geometry operations.
- UI pages require query `token` for tenant-scoped rendering.
- Export file storage is local filesystem under `logs/exports/`.

Key files changed
- app/domain/models.py
- app/domain/permissions.py
- app/services/inspection_service.py
- app/api/routers/inspection.py
- app/api/routers/ui.py
- app/web/templates/inspection_list.html
- app/web/templates/inspection_task_detail.html
- app/web/static/inspection_task.js
- app/web/static/ui.css
- app/main.py
- infra/migrations/versions/202602210007_phase1_to_phase6.py
- infra/scripts/demo_inspection_phase1.py
- infra/scripts/demo_common.py
