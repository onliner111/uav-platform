# Phase 38 Report

- Phase: `phase-38-delivery-onboarding-operations.md`
- Result: `DONE`
- Closed At (UTC): `2026-03-02T04:39:15.7859953Z`

## Delivered
- Rebuilt `/ui/platform` into a delivery-first onboarding operations console with:
  - `租户开通向导`
  - `标准配置包与模板中心`
  - `模式切换与交付交接`
  - `数据字典与治理总览`
- Added route-side onboarding context in `app/api/routers/ui.py`, including onboarding cards, recommended config packs, handoff panels, and org-unit type options.
- Added new client-side onboarding interactions in `app/web/static/platform_ui.js`:
  - create org unit
  - create role from template
  - create user and bind role/org-unit
  - config-pack selection
  - local demo/training/production mode switching
- Kept RBAC visibility matrix and governance export links in an admin-only advanced section instead of the main delivery path.
- Added phase38 UI regression coverage in `tests/test_ui_console.py`.
- Added replayable demo `infra/scripts/demo_phase38_delivery_onboarding_operations.py`.

## Verification
- `docker compose -f infra/docker-compose.yml run --rm --build app ruff check app tests infra/scripts`
- `docker compose -f infra/docker-compose.yml run --rm --build app mypy app`
- `docker compose -f infra/docker-compose.yml run --rm --build app pytest -q`
- `docker compose -f infra/docker-compose.yml up --build -d`
- `docker compose -f infra/docker-compose.yml run --rm --build -e APP_BASE_URL=http://app:8000 app-tools python infra/scripts/demo_phase38_delivery_onboarding_operations.py`
