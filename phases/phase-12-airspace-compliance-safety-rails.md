# Phase 12 - 空域合规与安全护栏

## 0. Basis
- Based on: `phases/phase-08-one-net-unified-flight-planning.md`
- Depends on: `phases/phase-11-unified-task-center-workflow.md`

## 1. Objective
构建平台级空域与安全护栏，确保任务计划与执行过程“可校验、可拦截、可留痕”。

## 2. Scope
- 禁飞区/限高区/敏感区模型与校验
- 飞前检查清单（Checklist）与审批策略联动
- 电子围栏策略与关键指令拦截
- 合规原因码与审计细节标准化

## 3. Out of Scope
- AI 风险预测与智能建议（Phase 14）
- 外部监管平台深度对接（Phase 15）

## 4. Deliverables
- 空域策略域模型与迁移链路
- 合规校验服务（任务创建/流转/执行拦截点）
- 飞前检查与围栏策略 API
- 合规场景测试与演示脚本

## 5. Acceptance
- 非法任务计划可被阻断并返回明确原因
- 应急快速通道在受控策略下可运行且全程留痕
- 合规审计可还原“谁在何时因何被拦截/放行”
- 核心路径无跨租户越权

## 6. Exit Criteria
- `ruff`, `mypy`, `pytest`, `e2e` 全绿
- 合规场景回归脚本可复跑

---

## 7. Priority Tuning (P0/P1/P2)

- P0（先做，阻塞后续阶段）：
  - `12-WP1` 空域区划模型与基础校验
  - `12-WP3` 指令前置校验与拦截原因码（最小护栏）
- P1（随后完成，强化流程合规）：
  - `12-WP2` 飞前检查清单与审批联动
  - `12-WP3` 审计字段标准化细化
- P2（可延后到本阶段后半）：
  - `12-WP3` 复杂围栏策略与高级规则组合
- 执行顺序：`P0 -> P1 -> P2 -> 12-WP4`

## 8. Execution Progress

- [x] 12-WP1 空域区划模型与基础校验
  - 区域实体（禁飞/限高/敏感）与查询
  - 任务计划时空冲突校验
- [x] 12-WP2 飞前检查清单与审批联动
  - Checklist 模型、模板、执行记录
  - 与任务审批策略打通
- [x] 12-WP3 围栏策略与执行期护栏
  - 指令前置校验与拦截
  - 原因码与审计字段规范化
- [x] 12-WP4 验收关账
  - 演示脚本：`infra/scripts/demo_phase12_airspace_compliance.py`
  - 报告：`logs/phase-12-airspace-compliance-safety-rails.md.report.md`
  - 全门禁复验通过
