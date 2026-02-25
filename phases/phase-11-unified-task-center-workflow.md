# Phase 11 - 统一任务中心工作流

## 0. Basis
- Based on: `phases/phase-08-one-net-unified-flight-planning.md`
- Depends on: `phases/phase-10-unified-map-situation-v1.md`

## 1. Objective
统一巡检、应急、测绘、安防等任务流程，实现“创建 -> 审批(可选) -> 执行 -> 验收 -> 归档”的标准化任务中心。

## 2. Scope
- 任务类型体系与模板中心
- 派单机制：手工指定 + 规则/评分自动匹配
- 生命周期状态机与任务资料（区域、风险、清单、附件）
- 多角色协同与审计留痕

## 3. Out of Scope
- 空域与围栏策略引擎（Phase 12）
- AI 自动生成总结与建议（Phase 14）

## 4. Deliverables
- 任务中心域模型与迁移链路
- 统一任务中心 API 与现有 mission/inspection/incident 对接
- 调度规则引擎（首版可配置）
- 端到端演示脚本与回归测试

## 5. Acceptance
- 多角色端到端流程可稳定跑通
- 手工与自动派单结果可解释
- 生命周期与责任归属全链路可审计
- 关键路径无跨租户越权

## 6. Exit Criteria
- `ruff`, `mypy`, `pytest`, `e2e` 全绿
- 任务中心演示脚本可复跑

---

## 7. Priority Tuning (P0/P1/P2)

- P0（先做，阻塞后续阶段）：
  - `11-WP1` 任务类型/模板中心建模
  - `11-WP2` 手工派单最小链路（先不引入复杂评分）
  - `11-WP3` 生命周期状态机核心流转
- P1（随后完成，强化自动化）：
  - `11-WP2` 规则/评分自动匹配
  - `11-WP3` 风险点与检查清单模型补齐
- P2（可延后到本阶段后半）：
  - `11-WP3` 附件能力增强与复杂协同细节
- 执行顺序：`P0 -> P1 -> P2 -> 11-WP4`

## 8. Execution Progress

- [x] 11-WP1 任务类型/模板中心建模
  - 统一任务类型字典与模板实体
  - 模板管理接口与权限接入
- [x] 11-WP2 派单与自动匹配引擎
  - 手工派单 API（P0 已完成）
  - 规则/评分匹配（基于资源池可用性，可解释评分已完成）
- [x] 11-WP3 生命周期与任务资料
  - 统一状态机与流转约束（P0 已完成）
  - 风险点、检查清单、附件模型（P1/P2 增强已完成：risk-checklist 更新、attachment/comment 协同）
- [x] 11-WP4 验收关账
  - 演示脚本：`infra/scripts/demo_phase11_task_center.py`
  - 报告：`logs/phase-11-unified-task-center-workflow.md.report.md`
  - 全门禁复验通过
