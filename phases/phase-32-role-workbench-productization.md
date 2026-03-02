# Phase 32 - 角色工作台产品化重构

## 0. Basis
- Based on: `项目最终目标.md`
- Depends on: `phases/phase-31-observability-reliability-ops-console.md`

## 1. Objective
将现有统一控制台重构为面向非技术业务人员长期使用的角色化产品入口，降低学习成本与误操作率。

## 2. Scope
- 按角色拆分首页与主入口：指挥员、调度员、飞手/值守、审核员/合规员、领导只读视图
- 全局导航中文化与业务术语统一
- 高频流程入口重排：按“今日待办 / 风险 / 核心动作”组织
- 从“参数/ID 驱动”迁移到“对象选择驱动”的基础交互模式
- 角色级首页摘要卡、待办区、风险提示与下一步建议
- 范围内现存主业务页全部按统一产品标准改造完成，不保留旧后台/调试式交互

## 3. Out of Scope
- 地图主界面重构（Phase 33）
- 移动端现场执行端（Phase 35）

## 4. Deliverables
- 角色工作台信息架构蓝图
- 多角色首页与工作台页面集
- 全站核心术语中文化规范
- 角色入口演示脚本与培训路径说明

## 5. Acceptance
- 不同角色登录后只看到与职责强相关的工作台入口
- 新用户在无技术培训情况下可理解页面结构与核心动作
- 主要任务入口不依赖记忆 API 路径或对象 ID

## 6. Product Delivery Standard
- 后续涉及的所有 UI 修改必须以“正式交付给非技术业务人员长期使用”为默认标准，不再接受仅面向内部联调的临时页面
- 默认交互必须采用“对象选择 + 向导/主动作 + 明确反馈”，不得把手填 ID、JSON、WKT、底层流程实例作为普通用户主路径
- 页面文案、按钮、提示、空态、导航必须保持中文化、简洁化、风格一致，沿用统一壳层与通用组件
- 不符合标准但仍需保留的能力，必须下沉为管理员高级模式或隐藏入口，不得继续作为主业务页面暴露
- 阶段范围内的遗留页面必须全部完成改造、下沉或移除后，才允许进入验收关账

## 7. Exit Criteria
- `ruff`, `mypy`, `pytest`, `e2e` 全绿
- Phase 32 范围内主业务页面全部达成正式交付标准，或已明确下沉为管理员模式
- 角色工作台演示脚本可复跑

---

## 8. Priority Tuning (P0/P1/P2)

- P0：
  - `32-WP1` 角色模型与首页信息架构定版
  - `32-WP2` 全局中文化与导航重组
- P1：
  - `32-WP3` 指挥员/调度员工作台落地
  - `32-WP4` 飞手/审核员/领导视图落地
- P2：
  - `32-WP5` 主业务页全部完成对象选择器与统一交互（含 Task / Alerts / Inspection / Defects / Assets / Compliance / Emergency）
- 执行顺序：`P0 -> P1 -> P2 -> 32-WP6`

## 9. Execution Progress

- [x] 32-WP1 角色模型与首页 IA
- [x] 32-WP2 全局中文化与导航重组
- [x] 32-WP3 指挥员/调度员工作台
- [x] 32-WP4 飞手/审核员/领导视图
- [x] 32-WP5 主业务页全部改造完成（Task / Alerts / Inspection / Defects / Assets / Compliance / Emergency 已完成统一交互收口）
- [x] 32-WP6 验收关账（已完成 `ruff` / `mypy` / 全量 `pytest -q` / `up --build -d` / `demo_phase32_role_workbench_productization.py`，并推进 checkpoint 至 `phase-33` `READY`）
