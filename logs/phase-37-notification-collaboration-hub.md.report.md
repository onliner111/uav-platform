# Phase 37 Report

- Phase: `phase-37-notification-collaboration-hub.md`
- Result: `DONE`
- Closed At (UTC): `2026-03-02T04:20:34.9326215Z`

## Delivered
- Rebuilt `/ui/alerts` into a collaboration-first notification hub with:
  - `消息中心与待办中心`
  - `统一待办视图`
  - `通知渠道与发送策略`
  - `回执、催办与升级跟踪`
  - `角色优先级与协同建议`
- Added route-side aggregation in `app/api/routers/ui.py` to combine alert, approval, and task reminders into unified to-do and message-center views while preserving existing alert operations.
- Kept existing alert actions and policy controls, but moved them behind collaboration-first information architecture in `app/web/templates/ui_alerts.html`.
- Updated interaction copy in `app/web/static/alerts_ui.js`.
- Added phase37 UI regression coverage in `tests/test_ui_console.py`.
- Added replayable demo `infra/scripts/demo_phase37_notification_collaboration_hub.py`.

## Verification
- `docker compose -f infra/docker-compose.yml run --rm --build app ruff check app tests infra/scripts`
- `docker compose -f infra/docker-compose.yml run --rm --build app mypy app`
- `docker compose -f infra/docker-compose.yml run --rm --build app pytest -q`
- `docker compose -f infra/docker-compose.yml up --build -d`
- `docker compose -f infra/docker-compose.yml run --rm --build -e APP_BASE_URL=http://app:8000 app-tools python infra/scripts/demo_phase37_notification_collaboration_hub.py`
