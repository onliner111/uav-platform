# Phase 17 Closeout Report

- Phase: `phase-17-multi-org-data-perimeter-v2.md`
- Closed at (UTC): `2026-02-26T18:33:13Z`
- Result: `DONE`

## Delivered Scope

1. `17-WP1`: org unit type + member-position model extension.
2. `17-WP2`: area/task/resource minimum perimeter loop (`resource_ids`).
3. `17-WP3`: platform super-admin cross-tenant governance + audit actions.
4. `17-P2`: role-inherited policy + explicit deny/allow conflict resolution.
5. `17-WP4`: full gate closeout and checkpoint transition.

## P2 Key Changes

1. Added user policy explicit-deny dimensions: `denied_org_unit_ids`, `denied_project_codes`, `denied_area_codes`, `denied_task_ids`, `denied_resource_ids`.
2. Added role policy model and APIs:
   - `GET /api/identity/roles/{role_id}/data-policy`
   - `PUT /api/identity/roles/{role_id}/data-policy`
3. Added effective policy API:
   - `GET /api/identity/users/{user_id}/data-policy:effective`
4. Enforced fixed resolution order in perimeter evaluation:
   - `explicit_deny > explicit_allow > inherited_allow > default_deny`
5. Added migration chain:
   - `202602260068/069/070`

## Verification

All passed via Docker Compose:

1. `docker compose -f infra/docker-compose.yml run --rm --build app ruff check app tests infra/scripts`
2. `docker compose -f infra/docker-compose.yml run --rm --build app mypy app`
3. `docker compose -f infra/docker-compose.yml run --rm --build app pytest -q`
4. `docker compose -f infra/docker-compose.yml up --build -d`
5. `docker compose -f infra/docker-compose.yml run --rm --build app alembic upgrade head`
6. `docker compose -f infra/docker-compose.yml run --rm --build app-tools python -m app.infra.openapi_export`
7. `docker compose -f infra/docker-compose.yml run --rm --build -e APP_BASE_URL=http://app:8000 app-tools python infra/scripts/demo_e2e.py`
8. `docker compose -f infra/docker-compose.yml run --rm --build -e APP_BASE_URL=http://app:8000 app-tools python infra/scripts/verify_smoke.py`
9. `docker compose -f infra/docker-compose.yml run --rm --build app-tools python infra/scripts/check_markdown_utf8.py`

## Checkpoint

- `phases/state.md` moved to:
  - `current_phase=phase-18-outcomes-repository-object-storage.md`
  - `status=READY`
- Current phase is closed and stopped, waiting for explicit next command.
