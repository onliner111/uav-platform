# Phase 15 - KPI 考核与开放平台

## 0. Basis
- Based on: `phases/phase-08-one-net-unified-flight-planning.md`
- Depends on: `phases/phase-14-ai-assistant-evidence-chain.md`

## 1. Objective
完善治理考核与对外集成能力，形成可运营、可对接、可持续迭代的平台交付基线。

## 2. Scope
- KPI 中心：时长、里程、完成率、闭环时长、利用率、故障率
- 事件/缺陷热力与对比分析
- 开放集成能力：Webhook、适配器、外部工单/资产系统接口
- API 治理文档与集成验收用例

## 3. Out of Scope
- 新增消息中间件与微服务拆分
- 复杂商业计费系统

## 4. Deliverables
- KPI 与热力分析域模型及聚合服务
- 开放平台 API/Webhook 契约与安全策略
- 外部系统联调示例（最少 1 条链路）
- 月/季治理报告模板与一键导出

## 5. Acceptance
- KPI 面板可按时间窗稳定产出指标
- 月度/季度治理报告可一键导出
- 至少 1 个外部系统联调 Demo 通过
- 核心路径无跨租户越权

## 6. Exit Criteria
- `ruff`, `mypy`, `pytest`, `e2e` 全绿
- KPI 与开放集成回归套件建立

---

## 7. Priority Tuning (P0/P1/P2)

- P0（先做，阻塞收官）：
  - `15-WP1` KPI 指标模型与聚合
  - `15-WP2` 开放接口安全治理最小集（契约+签名+审计）
- P1（随后完成，形成对外交付能力）：
  - `15-WP3` 外部系统联调样例（至少 1 条链路）
  - `15-WP3` 月/季治理报告模板
- P2（可延后到本阶段后半）：
  - `15-WP1` 高级对比分析与扩展热力专题
- 执行顺序：`P0 -> P1 -> P2 -> 15-WP4`

## 8. Execution Progress

- [x] 15-WP1 KPI 指标模型与聚合
  - 指标口径定义、聚合任务、查询 API
  - 热力图数据接口
- [x] 15-WP2 开放接口与安全治理
  - Webhook/Adapter 契约
  - API key/签名/审计策略
- [x] 15-WP3 外部系统联调与报告模板
  - 工单或资产系统联调样例
  - 月/季治理报告模板
- [x] 15-WP4 验收关账
  - 演示脚本：`infra/scripts/demo_phase15_kpi_open_platform.py`
  - 报告：`logs/phase-15-kpi-open-platform.md.report.md`
  - 全门禁复验通过
