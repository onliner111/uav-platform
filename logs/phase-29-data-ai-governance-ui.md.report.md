# phase-29-data-ai-governance-ui.md report

## Result
- Status: DONE
- Closed at (UTC): 2026-03-01T12:40:32Z

## Delivered Scope
- `29-WP1`: 数据成果与报告工作台落地于 `ui_reports`，覆盖 raw/outcome 检索、状态流转、版本查看、模板与导出任务操作。
- `29-WP2`: AI 治理核心页 `ui_ai_governance` 落地，覆盖模型目录、版本创建/晋升、任务与运行触发。
- `29-WP3`: 评估对比与回滚流程落地（评估重算、版本对比、rollout policy 回滚）。
- `29-WP4`: 证据链与复盘入口落地（输出 review bundle、evidence replay、人工审核动作）。
- `29-WP5`: 高级筛选增强落地（reports/ai 页多维过滤、导出列表状态过滤、AI 输出状态过滤）。
- `29-WP6`: 新增回放脚本 `infra/scripts/demo_phase29_data_ai_governance_ui.py` 并完成全链路关账验证。

## Quality Gates
- PASS: `docker compose -f infra/docker-compose.yml run --rm --build app ruff check app tests infra/scripts`
- PASS: `docker compose -f infra/docker-compose.yml run --rm --build app mypy app`
- PASS: `docker compose -f infra/docker-compose.yml run --rm --build app pytest -q`
- PASS: `docker compose -f infra/docker-compose.yml up --build -d`
- PASS: `docker compose -f infra/docker-compose.yml run --rm --build app alembic upgrade head`
- PASS: `docker compose -f infra/docker-compose.yml run --rm --build app-tools python -m app.infra.openapi_export`
- PASS: `docker compose -f infra/docker-compose.yml run --rm --build -e APP_BASE_URL=http://app:8000 app-tools python infra/scripts/demo_e2e.py`
- PASS: `docker compose -f infra/docker-compose.yml run --rm --build -e APP_BASE_URL=http://app:8000 app-tools python infra/scripts/verify_smoke.py`
- PASS: `docker compose -f infra/docker-compose.yml run --rm --build -e APP_BASE_URL=http://app:8000 app-tools python infra/scripts/verify_phase08_integration.py`
- PASS: `docker compose -f infra/docker-compose.yml run --rm --build -e APP_BASE_URL=http://app:8000 app-tools python infra/scripts/demo_phase25_observability_reliability.py`
- PASS: `docker compose -f infra/docker-compose.yml run --rm --build -e APP_BASE_URL=http://app:8000 app-tools python infra/scripts/demo_phase29_data_ai_governance_ui.py`
