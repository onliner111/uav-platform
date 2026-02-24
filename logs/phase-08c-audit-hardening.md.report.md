# Phase Report

- Phase: `phase-08c-audit-hardening.md`
- Status: `SUCCESS`

## What Was Delivered
- Standardized audit detail schema in middleware (`who/when/where/what/result`) and enabled contextual route-level audit enrichment.
- Added audit coverage for read-side export/download actions (`GET` paths containing `/export` or `/download`).
- Hardened identity critical-action audit trails:
  - data policy read/update audit enrichment with before/after policy snapshot and changed fields
  - cross-tenant deny reason normalization (`cross_tenant_boundary`)
  - new batch authorization API: `POST /api/identity/users/{user_id}/roles:batch-bind`
- Added regression tests for 08C audit hardening scenarios and synced API/Admin documentation.

## How To Verify
- `docker compose -f infra/docker-compose.yml run --rm --build app ruff check app tests infra/scripts`
- `docker compose -f infra/docker-compose.yml run --rm --build app mypy app`
- `docker compose -f infra/docker-compose.yml run --rm --build app pytest -q`
- `docker compose -f infra/docker-compose.yml up --build -d`
- `docker compose -f infra/docker-compose.yml run --rm --build app alembic upgrade head`
- `docker compose -f infra/docker-compose.yml run --rm --build app-tools python -m app.infra.openapi_export`
- `docker compose -f infra/docker-compose.yml run --rm --build -e APP_BASE_URL=http://app:8000 app-tools python infra/scripts/demo_e2e.py`
- `docker compose -f infra/docker-compose.yml run --rm --build -e APP_BASE_URL=http://app:8000 app-tools python infra/scripts/verify_smoke.py`

## Demos
- Identity data policy APIs:
  - `GET /api/identity/users/{user_id}/data-policy`
  - `PUT /api/identity/users/{user_id}/data-policy`
- Batch authorization API:
  - `POST /api/identity/users/{user_id}/roles:batch-bind`
- Audit evidence:
  - query `audit_logs` for actions `identity.data_policy.upsert` and `identity.user_role.batch_bind`

## Risks / Notes
- Docker Desktop npipe access may be transient in this environment; retry-on-denied remains required by repo rules.
- Batch bind returns mixed result statuses (`bound/already_bound/cross_tenant_denied/not_found`); consumers should use counters and per-item results together.
- Audit middleware remains non-blocking by design: audit write failures do not block request flow.

## Key Files Changed
- app/infra/audit.py
- app/api/routers/identity.py
- app/services/identity_service.py
- app/domain/models.py
- tests/test_identity.py
- docs/API_Appendix_V2.0.md
- docs/Admin_Manual_V2.0.md
