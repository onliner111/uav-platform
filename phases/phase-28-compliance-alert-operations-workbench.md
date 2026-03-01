# Phase 28 - 合规与告警运营工作台

## 0. Basis
- Based on: `项目最终目标.md`
- Depends on: `phases/phase-27-operations-ui-workflow-closure.md`

## 1. Objective
构建合规与告警运营台，支撑审批值守、空域治理、告警值班与升级处置的 UI 化运营。

## 2. Scope
- 审批中心：待办审批、批量处理、审计导出
- 空域策略中心：禁飞/限高/敏感区查看与管理
- 飞前检查中心：模板管理、任务检查执行视图
- 告警值班台：告警列表、ACK/CLOSE、值班排班、升级策略
- 复盘视图：告警路由、处置链、SLA 摘要

## 3. Out of Scope
- 成果库与 AI 模型治理深度页（Phase 29）
- 商业化计费与租户运营（Phase 30）

## 4. Deliverables
- 合规工作台与告警工作台页面集
- 值班/升级策略管理操作页
- 决策记录与审计导出入口
- 运营复盘演示脚本

## 5. Acceptance
- 值班员可在 UI 完成告警处置与升级
- 合规员可在 UI 查看策略、审批与决策记录
- 审计导出与复盘路径清晰可复现

## 6. Exit Criteria
- `ruff`, `mypy`, `pytest`, `e2e` 全绿
- 合规与告警运营演示脚本可复跑

---

## 7. Priority Tuning (P0/P1/P2)

- P0：
  - `28-WP1` 告警值班台核心动作闭环
  - `28-WP2` 审批中心待办与导出
- P1：
  - `28-WP3` 空域策略与飞前检查管理页
  - `28-WP4` 复盘与SLA视图
- P2：
  - `28-WP5` 批量操作与高级筛选
- 执行顺序：`P0 -> P1 -> P2 -> 28-WP6`

## 8. Execution Progress

- [x] 28-WP1 告警值班台闭环
- [x] 28-WP2 审批中心闭环
- [x] 28-WP3 空域与飞前检查管理
- [x] 28-WP4 复盘与SLA视图
- [x] 28-WP5 批量操作与高级筛选
- [x] 28-WP6 验收关账

## 9. Run Notes
- 2026-03-01T12:03:03Z (UTC): Completed `28-WP1`..`28-WP5` by delivering compliance and alert operations workbench closures in `ui_compliance`/`ui_alerts`: approval/flow actions, airspace and preflight operations, alert oncall/escalation/routing/silence/aggregation actions, review and SLA replay views, plus row-select and filter/batch ergonomics.
- 2026-03-01T12:03:03Z (UTC): Completed `28-WP6` closeout. Added replayable acceptance demo `infra/scripts/demo_phase28_compliance_alert_operations_workbench.py` and expanded UI RBAC regression (`tests/test_ui_console.py::test_ui_phase28_compliance_alert_workbench_write_visibility`).
- Verification:
  - `docker compose -f infra/docker-compose.yml run --rm --build app ruff check app tests infra/scripts`
  - `docker compose -f infra/docker-compose.yml run --rm --build app mypy app`
  - `docker compose -f infra/docker-compose.yml run --rm --build app pytest -q`
  - `docker compose -f infra/docker-compose.yml up --build -d`
  - `docker compose -f infra/docker-compose.yml run --rm --build app alembic upgrade head`
  - `docker compose -f infra/docker-compose.yml run --rm --build app-tools python -m app.infra.openapi_export`
  - `docker compose -f infra/docker-compose.yml run --rm --build -e APP_BASE_URL=http://app:8000 app-tools python infra/scripts/demo_e2e.py`
  - `docker compose -f infra/docker-compose.yml run --rm --build -e APP_BASE_URL=http://app:8000 app-tools python infra/scripts/verify_smoke.py`
  - `docker compose -f infra/docker-compose.yml run --rm --build -e APP_BASE_URL=http://app:8000 app-tools python infra/scripts/verify_phase08_integration.py`
  - `docker compose -f infra/docker-compose.yml run --rm --build -e APP_BASE_URL=http://app:8000 app-tools python infra/scripts/demo_phase25_observability_reliability.py`
  - `docker compose -f infra/docker-compose.yml run --rm --build -e APP_BASE_URL=http://app:8000 app-tools python infra/scripts/demo_phase28_compliance_alert_operations_workbench.py`
