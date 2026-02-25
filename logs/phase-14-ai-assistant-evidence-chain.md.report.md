# Phase 14 Report - AI 助手与证据链

- phase: `phase-14-ai-assistant-evidence-chain.md`
- status: `DONE`
- closed_at_utc: `2026-02-25T05:36:23Z`

## Scope Delivered

- `14-WP1` AI 任务与证据链建模
  - Added AI analysis job/run/output/evidence/review-action domain models and DTOs.
  - Added tenant-scoped + perimeter-aware visibility checks for AI artifacts.
  - Added migration chain with enum/range checks and tenant composite FK enforcement.
- `14-WP2` 摘要与建议流水线
  - Added AI pipeline service for run trigger, context snapshot, summary/suggestion generation, and persistence.
  - Added failure and retry workflow (`force_fail` + `retry` API) with retry-count controls.
  - Added evidence snapshots for model config/input/output/trace with hash chain.
- `14-WP3` 人审覆写与审计
  - Added human review API (`APPROVE`/`REJECT`/`OVERRIDE`) and persistent review action chain.
  - Added explicit audit context for review operations and responsibility fields.
  - Enforced `control_allowed=false` by model/service/migration constraints.
- `14-WP4` 验收关账
  - Delivered demo script `infra/scripts/demo_phase14_ai_evidence.py`.
  - Full gate chain rerun passed.

## Main Artifacts

- `app/services/ai_service.py`
- `app/api/routers/ai.py`
- `app/main.py`
- `app/domain/models.py`
- `infra/migrations/versions/202602250056_phase14_ai_evidence_expand.py`
- `infra/migrations/versions/202602250057_phase14_ai_evidence_backfill_validate.py`
- `infra/migrations/versions/202602250058_phase14_ai_evidence_enforce.py`
- `tests/test_ai_assistant.py`
- `infra/scripts/demo_phase14_ai_evidence.py`

## Acceptance Mapping

- AI 输出可追溯到输入与模型配置: PASS (evidence records + input/output hash chain).
- 人工审核可拦截/覆写 AI 建议: PASS (review action API + override payload + status transitions).
- 任何 AI 输出均不具备飞行控制权限: PASS (`control_allowed=false` default + check constraint).
- 核心路径无跨租户越权: PASS (tenant-scoped lookups and cross-tenant denial regression test).

## Verification Evidence

- `docker compose -f infra/docker-compose.yml run --rm --build app ruff check app tests infra/scripts` -> PASS
- `docker compose -f infra/docker-compose.yml run --rm --build app mypy app` -> PASS
- `docker compose -f infra/docker-compose.yml run --rm --build app pytest -q` -> PASS
- `docker compose -f infra/docker-compose.yml up --build -d` -> PASS
- `docker compose -f infra/docker-compose.yml run --rm --build app alembic upgrade head` -> PASS
- `docker compose -f infra/docker-compose.yml run --rm --build app-tools python -m app.infra.openapi_export` -> PASS
- `docker compose -f infra/docker-compose.yml run --rm --build -e APP_BASE_URL=http://app:8000 app-tools python infra/scripts/demo_e2e.py` -> PASS
- `docker compose -f infra/docker-compose.yml run --rm --build -e APP_BASE_URL=http://app:8000 app-tools python infra/scripts/verify_smoke.py` -> PASS
- `docker compose -f infra/docker-compose.yml run --rm --build -e APP_BASE_URL=http://app:8000 app-tools python infra/scripts/demo_phase14_ai_evidence.py` -> PASS
