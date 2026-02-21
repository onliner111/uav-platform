Phase: phase-03-emergency.md
Status: SUCCESS

What was delivered
- Added incident model + API and emergency one-click task creation flow with mission linkage.
- Implemented emergency UI entry page (`/ui/emergency`) with map point selection and rapid task creation action.

How to verify
- `docker --context default compose -f infra/docker-compose.yml run --rm --build -e APP_BASE_URL=http://app:8000 app-tools python infra/scripts/demo_emergency_phase3.py`

Demos
- Open `GET /ui/emergency?token=<jwt>`
- Create incident: `POST /api/incidents`
- Create task: `POST /api/incidents/{id}/create-task`

Risks/Notes
- Incident location is stored as text geometry representation.
- Emergency flow creates mission in `DRAFT` state for deterministic downstream control.

Key files changed
- app/services/incident_service.py
- app/api/routers/incident.py
- app/web/templates/emergency.html
- app/web/static/emergency.js
- app/domain/models.py
- infra/scripts/demo_emergency_phase3.py
