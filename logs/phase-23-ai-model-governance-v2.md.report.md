# Phase Report

- Phase: `phase-23-ai-model-governance-v2.md`
- Status: `SUCCESS`
- Completed at (UTC): `2026-02-27T16:11:17Z`

## What Was Delivered
- Delivered AI model governance v2 minimal loop (`23-WP1`..`23-WP3`) and closeout (`23-WP4`).
- Added AI governance domain and lifecycle:
  - `AiModelCatalog`, `AiModelVersion`, `AiModelRolloutPolicy`
  - `AiModelVersionStatus`: `DRAFT | CANARY | STABLE | DEPRECATED`
  - `AiAnalysisJob.model_version_id` binding
- Added model governance APIs:
  - `POST/GET /api/ai/models`
  - `POST/GET /api/ai/models/{model_id}/versions`
  - `POST /api/ai/models/{model_id}/versions/{version_id}:promote`
- Added rollout and threshold governance APIs:
  - `GET/PUT /api/ai/models/{model_id}/rollout-policy`
  - `POST /api/ai/jobs/{job_id}:bind-model-version`
  - run selection priority: `MANUAL_FORCE > JOB_BINDING > MODEL_DEFAULT`
- Added evaluation, rollback and scheduled tick APIs:
  - `POST /api/ai/evaluations:recompute`
  - `GET /api/ai/evaluations/compare`
  - `POST /api/ai/models/{model_id}/rollout-policy:rollback`
  - `POST /api/ai/jobs:schedule-tick`
- Added AI governance permissions and compatibility gate:
  - `ai.read`, `ai.write`
  - compatibility to `reporting.*` via `require_any_perm(...)`
- Added migration chain:
  - `202602270092/093/094` (`expand -> backfill/validate -> enforce`)
- Added phase demo:
  - `infra/scripts/demo_phase23_ai_model_governance_v2.py`
- Added regression coverage:
  - `tests/test_ai_assistant.py` (WP1/WP2/WP3 governance cases)

## How To Verify
- `docker compose -f infra/docker-compose.yml run --rm --build app ruff check app tests infra/scripts`
- `docker compose -f infra/docker-compose.yml run --rm --build app mypy app`
- `docker compose -f infra/docker-compose.yml run --rm --build app pytest -q`
- `docker compose -f infra/docker-compose.yml up --build -d`
- `docker compose -f infra/docker-compose.yml run --rm --build app alembic upgrade head`
- `docker compose -f infra/docker-compose.yml run --rm --build app-tools python -m app.infra.openapi_export`
- `docker compose -f infra/docker-compose.yml run --rm --build -e APP_BASE_URL=http://app:8000 app-tools python infra/scripts/demo_e2e.py`
- `docker compose -f infra/docker-compose.yml run --rm --build -e APP_BASE_URL=http://app:8000 app-tools python infra/scripts/verify_smoke.py`
- `docker compose -f infra/docker-compose.yml run --rm --build -e APP_BASE_URL=http://app:8000 app-tools python infra/scripts/verify_phase08_integration.py`
- `docker compose -f infra/docker-compose.yml run --rm --build -e APP_BASE_URL=http://app:8000 app-tools python infra/scripts/demo_phase23_ai_model_governance_v2.py`

## Key Files Changed
- `app/domain/models.py`
- `app/domain/permissions.py`
- `app/api/deps.py`
- `app/api/routers/ai.py`
- `app/services/ai_service.py`
- `tests/test_ai_assistant.py`
- `infra/migrations/versions/202602270092_phase23_wp1_ai_model_governance_expand.py`
- `infra/migrations/versions/202602270093_phase23_wp1_ai_model_governance_backfill_validate.py`
- `infra/migrations/versions/202602270094_phase23_wp1_ai_model_governance_enforce.py`
- `infra/scripts/demo_phase23_ai_model_governance_v2.py`
- `phases/phase-23-ai-model-governance-v2.md`
