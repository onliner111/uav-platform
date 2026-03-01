# Phase 27 - 运行域 UI 流程闭环

## 0. Basis
- Based on: `项目最终目标.md`
- Depends on: `phases/phase-26-ui-information-architecture-design-system.md`

## 1. Objective
把任务、巡查、缺陷、应急、资产维护的高频动作迁移到 UI 闭环，降低对 API 手工调用依赖。

## 2. Scope
- 任务中心：创建、派发、状态流转、评论与附件、历史视图
- 巡查与缺陷：从发现到整改到复核的页面化操作链
- 应急流程：事件创建、应急任务发起、关键状态更新
- 资产与维护：可用性/健康度更新、工单管理与追踪
- 跨页面联动：从态势到处置再到任务归档

## 3. Out of Scope
- 合规审批编排深度配置（Phase 28）
- 报表与治理类深度配置（Phase 29+）

## 4. Deliverables
- 任务/巡查/缺陷/应急/资产深页 UI
- 关键写操作表单与确认流程
- 页面级审计动作映射清单
- 端到端演示脚本（运行域闭环）

## 5. Acceptance
- 调度员可仅通过 UI 完成主要运行域闭环
- 关键动作具备反馈、错误提示、重试路径
- 写操作通过 RBAC 与审计校验

## 6. Exit Criteria
- `ruff`, `mypy`, `pytest`, `e2e` 全绿
- 运行域 UI 闭环演示脚本可复跑

---

## 7. Priority Tuning (P0/P1/P2)

- P0：
  - `27-WP1` 任务中心写操作闭环
  - `27-WP2` 资产与维护高频操作闭环
- P1：
  - `27-WP3` 巡查/缺陷/应急跨页面联动
  - `27-WP4` 操作反馈与错误处理统一
- P2：
  - `27-WP5` 批量操作与快捷动作增强
- 执行顺序：`P0 -> P1 -> P2 -> 27-WP6`

## 8. Execution Progress

- [x] 27-WP1 任务中心写操作闭环
- [x] 27-WP2 资产与维护闭环
- [x] 27-WP3 巡查/缺陷/应急联动
- [x] 27-WP4 反馈与错误处理统一
- [x] 27-WP5 批量与快捷增强
- [x] 27-WP6 验收关账

## 9. Run Notes
- 2026-03-01T05:26:00Z (UTC): Completed `27-WP3`..`27-WP5` by delivering operations deep-page closure across inspection/defect/emergency and quick-create actions on inspection list. Added write-gated forms and cross-page links in `inspection_task_detail.html`, `defects.html`, `emergency.html`, and `inspection_list.html`; unified interaction/error feedback through `UIActionUtils` in `inspection_task.js`, `defects.js`, `emergency.js`, and new `inspection_list.js`.
- 2026-03-01T05:26:00Z (UTC): Completed `27-WP6` closeout. Added replayable acceptance demo `infra/scripts/demo_phase27_operations_ui_closure.py` (inspection -> defect -> incident/task -> task-center -> asset maintenance -> UI route checks) and expanded UI RBAC regression `tests/test_ui_console.py::test_ui_execute_pages_readonly_mode_hides_write_actions`.
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
  - `docker compose -f infra/docker-compose.yml run --rm --build -e APP_BASE_URL=http://app:8000 app-tools python infra/scripts/demo_phase27_operations_ui_closure.py`
