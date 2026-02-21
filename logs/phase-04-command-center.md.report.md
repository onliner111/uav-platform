Phase: phase-04-command-center.md
Status: SUCCESS

What was delivered
- Added dashboard stats API + WebSocket stream (`/api/dashboard/stats`, `/ws/dashboard`) and observation feed.
- Implemented fullscreen command center UI (`/ui/command-center`) with realtime stat + map updates.

How to verify
- `docker --context default compose -f infra/docker-compose.yml run --rm --build -e APP_BASE_URL=http://app:8000 app-tools python infra/scripts/demo_command_center_phase4.py`

Demos
- Open `GET /ui/command-center?token=<jwt>`
- Stream data from `WS /ws/dashboard?token=<jwt>`

Risks/Notes
- Dashboard push strategy is periodic polling in websocket loop (2s cadence).
- Online device count currently derives from registered drones, not active telemetry heartbeat.

Key files changed
- app/services/dashboard_service.py
- app/api/routers/dashboard.py
- app/web/templates/command_center.html
- app/web/static/command_center.js
- infra/scripts/demo_command_center_phase4.py
