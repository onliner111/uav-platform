# Phase 29 - 数据成果与 AI 治理 UI

## 0. Basis
- Based on: `项目最终目标.md`
- Depends on: `phases/phase-28-compliance-alert-operations-workbench.md`

## 1. Objective
形成“成果可管、报告可出、模型可治”的 UI 运营能力，支持数据资产与 AI 治理的日常工作。

## 2. Scope
- 成果库：原始数据、成果版本、状态与生命周期视图
- 报告中心：模板管理、导出任务、导出结果追踪
- AI 治理：模型目录、版本、灰度策略、评估对比、回滚入口
- 证据链展示：模型版本、阈值、输入摘要、审计记录

## 3. Out of Scope
- 商业化运营与计费策略页（Phase 30）
- 运维可靠性运营台（Phase 31）

## 4. Deliverables
- 成果库管理页与报告中心页
- AI 模型治理页面集
- 证据链可视化与复盘入口
- 数据与 AI 治理演示脚本

## 5. Acceptance
- 业务人员可在 UI 完成成果检索与报告导出
- AI 运营人员可在 UI 完成版本治理与回滚
- 关键 AI 决策可在 UI 可追溯

## 6. Exit Criteria
- `ruff`, `mypy`, `pytest`, `e2e` 全绿
- 数据与 AI 治理演示脚本可复跑

---

## 7. Priority Tuning (P0/P1/P2)

- P0：
  - `29-WP1` 成果库与报告中心核心页
  - `29-WP2` AI 模型版本治理核心页
- P1：
  - `29-WP3` 评估对比与回滚流程页
  - `29-WP4` 证据链可视化
- P2：
  - `29-WP5` 高级筛选与批量治理增强
- 执行顺序：`P0 -> P1 -> P2 -> 29-WP6`

## 8. Execution Progress

- [x] 29-WP1 成果库与报告中心
- [x] 29-WP2 AI 模型治理核心页
- [x] 29-WP3 评估对比与回滚流程
- [x] 29-WP4 证据链可视化
- [x] 29-WP5 高级筛选与批量增强
- [x] 29-WP6 验收关账
