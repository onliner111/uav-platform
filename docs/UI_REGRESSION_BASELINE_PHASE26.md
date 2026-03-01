# UI Regression Baseline (Phase 26)

## 1. Purpose
- Provide a stable regression baseline for phase-26 UI IA/design-system work.
- Keep future UI phases (27+) from regressing session, navigation, RBAC visibility, and key interaction surfaces.

## 2. Baseline Command
- `docker compose -f infra/docker-compose.yml run --rm --build app pytest -q tests/test_ui_console.py`

## 3. Covered Regression Dimensions
- Session flow:
  - login/session cookie
  - logout/csrf
  - legacy query-token compatibility
- Navigation IA:
  - grouped navigation rendering (`Overview/Observe/Execute/Govern/Platform`)
  - shell accessibility markers (`skip link`, navigation aria labels)
- RBAC visibility:
  - menu visibility and route guard
  - action-level visibility (`task-center` write actions hidden for read-only permission)
  - platform RBAC matrix rendering
- UI baseline assets:
  - shared interaction helper script loaded in shell (`/static/ui_action_helpers.js`)

## 4. Extension Rule
- New UI modules added in later phases must add assertions into `tests/test_ui_console.py` or a dedicated UI regression file.
- Any new mutating page should include both:
  - write-action visibility assertion (permission on/off)
  - failure/success interaction-state assertion where feasible.

