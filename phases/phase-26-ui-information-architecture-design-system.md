# Phase 26 - UI 信息架构与设计系统

## 0. Basis
- Based on: `项目最终目标.md`
- Depends on: `phases/phase-25-observability-reliability.md`

## 1. Objective
建立统一、可扩展、可运营的 UI 基础层，确保后续业务页面按一致的交互与视觉规则持续交付。

## 2. Scope
- 控制台 IA（信息架构）重构：导航分组、角色入口、跨模块路径
- 设计系统基座：颜色/排版/间距/组件状态规范
- 组件层规范：表格、表单、筛选器、状态标签、空态/错误态、操作反馈
- RBAC 页面可见性与动作可见性规范（读/写/审批/管理）
- UI 质量基线：可访问性、移动端、性能与回归策略

## 3. Out of Scope
- 全量业务流程深度改造（由后续阶段承担）
- 前端技术栈切换（保持现有轻量栈）

## 4. Deliverables
- IA 文档与页面路由分层图
- 设计 Token 与组件规范文档
- UI 页面模板升级（列表/详情/操作页骨架）
- RBAC 可见性矩阵（页面级 + 动作级）
- UI 回归清单与验收脚本

## 5. Acceptance
- 用户能在 3 次点击内到达高频模块入口
- 关键页面具备统一视觉与交互规范
- 角色差异在 UI 层可解释且可验证
- 移动端关键页面可用

## 6. Exit Criteria
- `ruff`, `mypy`, `pytest`, `e2e` 全绿
- UI 验收清单与截图证据可复跑

---

## 7. Priority Tuning (P0/P1/P2)

- P0（先做，阻塞后续 UI 扩展）：
  - `26-WP1` IA 与导航分组定版
  - `26-WP2` 设计 Token 与基础组件标准化
- P1（随后完成，形成可执行规范）：
  - `26-WP3` 列表页/操作页统一交互模式
  - `26-WP4` RBAC UI 可见性矩阵与校验
- P2（可延后到本阶段后半）：
  - `26-WP5` 移动端与可访问性优化
  - `26-WP6` UI 回归测试基线完善
- 执行顺序：`P0 -> P1 -> P2 -> 26-WP7`

## 8. Execution Progress

- [x] 26-WP1 IA 与导航分组
- [x] 26-WP2 设计 Token 与组件标准化
- [x] 26-WP3 列表页/操作页交互统一
- [x] 26-WP4 RBAC UI 可见性矩阵
- [x] 26-WP5 移动端与可访问性优化
- [x] 26-WP6 UI 回归测试基线
- [x] 26-WP7 验收关账

## 9. Run Notes
- 2026-02-28T20:45:51Z (UTC): Completed `26-WP1` (console IA regrouping) by introducing grouped navigation model (`Overview/Observe/Execute/Govern/Platform`) and grouped module entry rendering in console shell. Updated files: `app/api/routers/ui.py`, `app/web/templates/console_base.html`, `app/web/templates/ui_console.html`, `app/web/static/ui.css`.
- Verification:
  - `docker compose -f infra/docker-compose.yml run --rm --build app pytest -q tests/test_ui_console.py`
- 2026-02-28T20:59:44Z (UTC): Completed `26-WP6` (UI regression baseline hardening). Added phase-26 regression baseline document `docs/UI_REGRESSION_BASELINE_PHASE26.md`, expanded `tests/test_ui_console.py` with navigation/a11y markers and platform RBAC matrix assertions, and revalidated UI console regression chain.
- Verification:
  - `docker compose -f infra/docker-compose.yml run --rm --build app ruff check app/api/routers/ui.py tests/test_ui_console.py`
  - `docker compose -f infra/docker-compose.yml run --rm --build app pytest -q tests/test_ui_console.py`
- 2026-02-28T21:09:17Z (UTC): Completed `26-WP7` closeout. Full quality gates and regression chain passed:
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
- 2026-02-28T20:55:18Z (UTC): Completed `26-WP4` (RBAC UI visibility matrix + validation). Added central visibility matrix definitions in `app/api/routers/ui.py`, exposed resolved view/write permissions to platform page, rendered matrix table in `app/web/templates/ui_platform.html`, and added action-level RBAC regression in `tests/test_ui_console.py::test_ui_task_center_action_visibility_by_write_permission`.
- Verification:
  - `docker compose -f infra/docker-compose.yml run --rm --build app ruff check app/api/routers/ui.py tests/test_ui_console.py`
  - `docker compose -f infra/docker-compose.yml run --rm --build app mypy app/api/routers/ui.py`
  - `docker compose -f infra/docker-compose.yml run --rm --build app pytest -q tests/test_ui_console.py`
- 2026-02-28T20:57:19Z (UTC): Completed `26-WP5` (mobile and accessibility optimization). Added skip-link and navigation accessibility labels in `console_base.html`, live-region semantics for quick-action result components, keyboard escape handling for mobile sidebar in `console_shell.js`, and reduced-motion support plus accessibility styles in `ui.css`.
- Verification:
  - `docker compose -f infra/docker-compose.yml run --rm --build app pytest -q tests/test_ui_console.py`
- 2026-02-28T20:52:40Z (UTC): Completed `26-WP3` (list/action interaction unification). Added shared UI action helper (`app/web/static/ui_action_helpers.js`) for result severity (`success/warn/danger`), busy-button states, and normalized error messaging; wired Task Center/Assets/Alerts quick-action scripts to the shared pattern and standardized action result slots across related templates.
- Verification:
  - `docker compose -f infra/docker-compose.yml run --rm --build app pytest -q tests/test_ui_console.py`
  - `docker compose -f infra/docker-compose.yml run --rm --build app ruff check app/api/routers/ui.py`
  - `docker compose -f infra/docker-compose.yml run --rm --build app mypy app/api/routers/ui.py`
- 2026-02-28T20:49:00Z (UTC): Completed `26-WP2` (design token/component baseline). Added token scale and primitive component classes in `app/web/static/ui.css` (typography/spacing/radius/focus-ring + section/action/field/kpi primitives), applied KPI/section primitives across core UI pages, and added design baseline documentation `docs/UI_DESIGN_SYSTEM_BASELINE.md`.
- Verification:
  - `docker compose -f infra/docker-compose.yml run --rm --build app pytest -q tests/test_ui_console.py`
