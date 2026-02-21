Phase: phase-02-defect-closure.md
Status: SUCCESS

What was delivered
- Added defect + defect_actions model support and integrated migration.
- Implemented defect workflow APIs (create from observation, assign, state transitions, detail with action history, stats) and `/ui/defects`.

How to verify
- `docker --context default compose -f infra/docker-compose.yml run --rm --build -e APP_BASE_URL=http://app:8000 app-tools python infra/scripts/demo_defect_phase2.py`

Demos
- Open `GET /ui/defects?token=<jwt>`
- Check `GET /api/defects/stats`

Risks/Notes
- Review-task creation is auto-triggered at `FIXED` using existing task template linkage.
- State machine is strict linear flow (`OPEN -> ASSIGNED -> IN_PROGRESS -> FIXED -> VERIFIED -> CLOSED`).

Key files changed
- app/services/defect_service.py
- app/api/routers/defect.py
- app/web/templates/defects.html
- app/web/static/defects.js
- app/domain/models.py
- infra/scripts/demo_defect_phase2.py
