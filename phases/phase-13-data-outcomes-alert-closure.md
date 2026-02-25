# Phase 13 - 数据成果与告警处置闭环

## 0. Basis
- Based on: `phases/phase-08-one-net-unified-flight-planning.md`
- Depends on: `phases/phase-12-airspace-compliance-safety-rails.md`

## 1. Objective
建设统一成果库与告警处置链路，实现“数据可管理、告警可闭环、报告可追溯”。

## 2. Scope
- 原始数据与成果数据统一目录
- 结构化成果字段（点位/类型/置信度/状态）
- 告警分级（P1/P2/P3）与值守路由
- 闭环流程：告警 -> 处置 -> 验证 -> 复盘
- 报告导出增强（按任务/时间窗/专题）

## 3. Out of Scope
- AI 模型推理与自动建议（Phase 14）
- 对外开放平台能力（Phase 15）

## 4. Deliverables
- 成果与告警闭环域模型及迁移链路
- 告警分级与值守路由服务
- 处置闭环 API 与报告导出增强
- 端到端闭环演示脚本与回归测试

## 5. Acceptance
- 告警全生命周期可追溯并可复盘
- 成果可按任务与时间窗检索并导出
- 数据与处置链路可追踪到责任人与时间线
- 核心路径无跨租户越权

## 6. Exit Criteria
- `ruff`, `mypy`, `pytest`, `e2e` 全绿
- 数据成果与告警闭环演示脚本可复跑

---

## 7. Priority Tuning (P0/P1/P2)

- P0（先做，阻塞后续阶段）：
  - `13-WP1` 成果目录与结构化模型
  - `13-WP2` 告警分级与值守路由（先做站内闭环）
- P1（随后完成，强化闭环）：
  - `13-WP3` 处置动作链与复盘记录
  - `13-WP3` 报告导出按任务/时间窗增强
- P2（可延后到本阶段后半或下阶段联调）：
  - `13-WP2` 外部通知通道适配细节（短信/邮件/企微/钉钉）
- 执行顺序：`P0 -> P1 -> P2 -> 13-WP4`

## 8. Execution Progress

- [ ] 13-WP1 成果目录与结构化模型
  - 原始数据/成果数据索引模型
  - 结构化字段与状态机
- [ ] 13-WP2 告警分级与值守路由
  - P1/P2/P3 策略与值班规则
  - 通知接口预留（短信/邮件/企微/钉钉）
- [ ] 13-WP3 处置闭环与报告增强
  - 处置动作链与复盘记录
  - 报告导出按任务/周期/专题增强
- [ ] 13-WP4 验收关账
  - 演示脚本：`infra/scripts/demo_phase13_data_alert_closure.py`
  - 报告：`logs/phase-13-data-outcomes-alert-closure.md.report.md`
  - 全门禁复验通过
