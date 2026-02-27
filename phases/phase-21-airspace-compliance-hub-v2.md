# Phase 21 - 空域合规中枢 v2

## 0. Basis
- Based on: `111.md`
- Depends on: `phases/phase-20-task-center-v2-optimization.md`

## 1. Objective
将现有合规能力升级为可配置、可复盘的中枢体系，支持多层级策略与审批流治理。

## 2. Scope
- 多层级空域策略（平台/租户/组织）
- 可配置审批流编排
- 飞前检查模板与执行规则增强
- 合规证据链完善（规则命中、审批、放行/拦截）
- 合规与任务中心联动增强

## 2.1 Design Constraints (Execution Guardrails)
- 严守租户边界：不引入跨租户共享策略表；“平台级”仅作为同租户默认基线配置（platform default）。
- 三层策略采用固定裁决顺序：`org_unit override > tenant override > platform default`，且 `deny > allow`。
- 先兼容后升级：P0/P1 阶段默认不强依赖 Mission 新状态；审批流程通过审批实例驱动，最终落在既有 `APPROVED/REJECTED`。
- 所有新增治理能力按 `expand -> backfill/validate -> enforce` 三段迁移落地。

## 3. Out of Scope
- 外部政务审批系统深度双向同步
- 实时复杂规则引擎平台化改造

## 4. Deliverables
- 合规策略分层模型与 API
  - 策略配置实体（platform default / tenant / org_unit）
  - 解析与裁决服务（含命中解释字段）
- 审批流配置与执行增强
  - 审批流模板（步骤、审批角色/条件）
  - 审批实例与动作 API（approve/reject/rollback）
- 飞前检查模板中心增强
  - 模板版本化与证据要求（最小必填证据规则）
- 合规证据链导出与审计回归测试
  - 合规决策记录（rule_hits / decision / reason_code / actor / source）
  - 导出接口与回归脚本
- 合规与任务中心联动
  - mission-linked task 写入合规快照（context_data）

## 5. Acceptance
- 多层级策略可稳定生效并可解释
- 审批流可按租户配置并可追踪
- 飞前检查可阻断不合规任务
- 全流程具备可复盘证据链
- 核心链路保持租户隔离，无跨租户越权

## 6. Exit Criteria
- `ruff`, `mypy`, `pytest`, `e2e` 全绿
- 合规中枢 v2 演示脚本可复跑

---

## 7. Priority Tuning (P0/P1/P2)

- P0（先做，阻塞安全放行链路）：
  - `21-WP1` 多层级空域策略最小闭环
    - 新增三层策略配置与解析器（platform default / tenant / org_unit）
    - 在 `mission create/update` 与 `command precheck` 接入统一裁决
    - 输出命中解释（命中层级、命中规则、最终决策）
  - `21-WP2` 审批流可配置最小链路
    - 新增审批流模板与实例（最少二步审批）
    - 支持 `approve/reject/rollback` 动作与审计落点
    - 与 mission 审批兼容：先不强依赖新 mission 状态，最终回写 `APPROVED/REJECTED`
- P1（随后完成，形成治理闭环）：
  - `21-WP3` 飞前检查体系增强 + 合规证据链导出与追踪增强
    - 飞前检查模板版本化与证据要求校验
    - 合规决策记录模型/API/导出
    - 任务中心联动：mission 关联任务写入合规快照与原因码
- P2（可延后到本阶段后半）：
  - 在 `21-WP1` 基础上补齐复杂策略组合与冲突裁决优化
  - 可选引入 mission `APPROVAL_PENDING` 状态（仅在收益明显且迁移风险可控时启用）
- 执行顺序：`P0 -> P1 -> P2 -> 21-WP4`

## 8. Execution Progress

- [x] 21-WP1 多层级空域策略最小闭环
- [x] 21-WP2 审批流可配置最小链路
- [x] 21-WP3 飞前检查与证据链增强
- [x] 21-WP4 验收关账
