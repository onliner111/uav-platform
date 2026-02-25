# Phase 15 Report - KPI 考核与开放平台

- phase: `phase-15-kpi-open-platform.md`
- status: `DONE`
- closed_at_utc: `2026-02-25T06:03:33Z`

## Scope Delivered

- `15-WP1` KPI 指标模型与聚合
  - Added KPI snapshot/heatmap domain models and migration chain.
  - Added KPI aggregation service over missions/mission-runs/alerts/outcomes/telemetry events.
  - Added KPI APIs: recompute/list/latest snapshot and heatmap query.
- `15-WP2` 开放接口与安全治理
  - Added open-platform credentials/webhooks/delivery/adapter-ingress models and APIs.
  - Added API key + HMAC-SHA256 signature verification for adapter ingress.
  - Added webhook test-dispatch with signed header simulation and auditable delivery logs.
- `15-WP3` 外部系统联调与报告模板
  - Added governance monthly/quarterly export template API from KPI snapshots.
  - Added external integration sample chain (credential -> webhook dispatch -> adapter ingest).
- `15-WP4` 验收关账
  - Delivered demo script `infra/scripts/demo_phase15_kpi_open_platform.py`.
  - Full gate chain rerun passed.

## Main Artifacts

- `app/services/kpi_service.py`
- `app/services/open_platform_service.py`
- `app/api/routers/kpi.py`
- `app/api/routers/open_platform.py`
- `app/domain/models.py`
- `app/main.py`
- `infra/migrations/versions/202602250059_phase15_kpi_open_platform_expand.py`
- `infra/migrations/versions/202602250060_phase15_kpi_open_platform_backfill_validate.py`
- `infra/migrations/versions/202602250061_phase15_kpi_open_platform_enforce.py`
- `tests/test_kpi_open_platform.py`
- `infra/scripts/demo_phase15_kpi_open_platform.py`

## Acceptance Mapping

- KPI 面板可按时间窗稳定产出指标: PASS (`/api/kpi/snapshots/recompute` + `/api/kpi/snapshots*`).
- 月度/季度治理报告可一键导出: PASS (`/api/kpi/governance/export`).
- 至少 1 个外部系统联调 Demo 通过: PASS (signed adapter ingress + webhook dispatch in phase15 demo).
- 核心路径无跨租户越权: PASS (tenant-scoped credential/webhook/event lookups + tenant composite FK constraints).

## Verification Evidence

- `docker compose -f infra/docker-compose.yml run --rm --build app ruff check app tests infra/scripts` -> PASS
- `docker compose -f infra/docker-compose.yml run --rm --build app mypy app` -> PASS
- `docker compose -f infra/docker-compose.yml run --rm --build app pytest -q` -> PASS
- `docker compose -f infra/docker-compose.yml up --build -d` -> PASS
- `docker compose -f infra/docker-compose.yml run --rm --build app alembic upgrade head` -> PASS
- `docker compose -f infra/docker-compose.yml run --rm --build app-tools python -m app.infra.openapi_export` -> PASS
- `docker compose -f infra/docker-compose.yml run --rm --build -e APP_BASE_URL=http://app:8000 app-tools python infra/scripts/demo_e2e.py` -> PASS
- `docker compose -f infra/docker-compose.yml run --rm --build -e APP_BASE_URL=http://app:8000 app-tools python infra/scripts/verify_smoke.py` -> PASS
- `docker compose -f infra/docker-compose.yml run --rm --build -e APP_BASE_URL=http://app:8000 app-tools python infra/scripts/demo_phase15_kpi_open_platform.py` -> PASS
