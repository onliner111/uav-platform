# Phase 14 - AI 助手与证据链

## 0. Basis
- Based on: `phases/phase-08-one-net-unified-flight-planning.md`
- Depends on: `phases/phase-13-data-outcomes-alert-closure.md`

## 1. Objective
引入非实时 AI 助手能力，确保结果“可解释、可审计、可回溯”，并保持人工可控。

## 2. Scope
- 离线/准实时分析任务编排
- 任务摘要与处置建议生成
- 证据链：模型版本、阈值、输入哈希、输出摘要
- 人审与覆写机制（human-in-the-loop）

## 3. Out of Scope
- AI 直接控制实时飞行或指令下发
- 大规模模型训练平台建设

## 4. Deliverables
- AI 分析任务与证据链域模型
- AI 结果查询/审核/覆写 API
- 摘要与建议生成流程（可替换模型适配层）
- 证据链一致性测试与演示脚本

## 5. Acceptance
- AI 输出可追溯到输入与模型配置
- 人工审核可拦截/覆写 AI 建议
- 任何 AI 输出均不具备飞行控制权限
- 核心路径无跨租户越权

## 6. Exit Criteria
- `ruff`, `mypy`, `pytest`, `e2e` 全绿
- AI 证据链完整性校验通过

---

## 7. Priority Tuning (P0/P1/P2)

- P0（先做，阻塞后续阶段）：
  - `14-WP1` AI 任务与证据链建模
  - `14-WP3` 人审覆写与审计（先保证“人工兜底”）
- P1（随后完成，形成业务价值）：
  - `14-WP2` 摘要与建议流水线
  - `14-WP3` 审核流程细化与责任追踪增强
- P2（可延后到本阶段后半）：
  - `14-WP2` 准实时优化与复杂重试编排
- 执行顺序：`P0 -> P1 -> P2 -> 14-WP4`

## 8. Execution Progress

- [ ] 14-WP1 AI 任务与证据链建模
  - AI job/run/output/evidence 模型
  - 租户与数据边界约束
- [ ] 14-WP2 摘要与建议流水线
  - 离线/准实时处理流程
  - 结果持久化与重试机制
- [ ] 14-WP3 人审覆写与审计
  - 审核/驳回/覆写 API
  - 审计明细与责任追踪
- [ ] 14-WP4 验收关账
  - 演示脚本：`infra/scripts/demo_phase14_ai_evidence.py`
  - 报告：`logs/phase-14-ai-assistant-evidence-chain.md.report.md`
  - 全门禁复验通过
