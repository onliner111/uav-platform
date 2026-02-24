# Phase 09 Readiness Checklist

## Scope Baseline
- [x] Phase 08A/08B/08C capabilities completed and gate-verified
- [x] Phase 08D integration acceptance script available (`infra/scripts/verify_phase08_integration.py`)
- [x] OpenAPI export command is reproducible in Docker toolchain

## Data Model Inputs (Asset Management)
- [x] Define core asset entities: UAV / payload / battery / controller / dock
- [x] Define tenant-scoped resource availability fields (region/org/project)
- [x] Define maintenance work-order model and history model
- [x] Define migration chain plan (`expand -> backfill/validate -> enforce`)

## API Contract Inputs
- [x] Asset lifecycle APIs (register, bind, unbind, retire)
- [x] Health and availability APIs (online/health/version/maintenance due)
- [x] Resource-pool query API (`what can fly where now`)
- [x] Maintenance work-order APIs

## Security & Governance Inputs
- [x] Tenant isolation baseline inherited from 08B/08C
- [x] RBAC baseline inherited from 08A
- [x] Audit coverage baseline inherited from 08C
- [x] Define Phase 09 critical actions audit matrix

## Test & Demo Inputs
- [x] Unit/integration tests for asset lifecycle and tenant isolation
- [x] E2E demo path for resource pool + maintenance closure
- [x] Regression inclusion in baseline Docker gate chain

## Gate Commands Baseline
- `docker compose -f infra/docker-compose.yml run --rm --build app ruff check app tests infra/scripts`
- `docker compose -f infra/docker-compose.yml run --rm --build app mypy app`
- `docker compose -f infra/docker-compose.yml run --rm --build app pytest -q`
- `docker compose -f infra/docker-compose.yml up --build -d`
- `docker compose -f infra/docker-compose.yml run --rm --build app alembic upgrade head`
- `docker compose -f infra/docker-compose.yml run --rm --build app-tools python -m app.infra.openapi_export`
- `docker compose -f infra/docker-compose.yml run --rm --build -e APP_BASE_URL=http://app:8000 app-tools python infra/scripts/demo_e2e.py`
- `docker compose -f infra/docker-compose.yml run --rm --build -e APP_BASE_URL=http://app:8000 app-tools python infra/scripts/verify_smoke.py`
- `docker compose -f infra/docker-compose.yml run --rm --build -e APP_BASE_URL=http://app:8000 app-tools python infra/scripts/verify_phase08_integration.py`
