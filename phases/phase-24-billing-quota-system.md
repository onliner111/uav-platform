# Phase 24 - 计费与配额系统

## 0. Basis
- Depends on: `phases/phase-23-ai-model-governance-v2.md`

## 1. Objective
建立可商用 SaaS 所需的套餐、配额、计量与账单能力，支撑商业化交付。

## 2. Scope
- 套餐与订阅管理
- 配额限制（用户/设备/任务/存储）
- 用量采集与计量聚合
- 账单生成与账期结算基础能力
- 配额命中审计与告警联动

## 3. Out of Scope
- 完整支付网关与发票系统
- 复杂多币种结算

## 4. Deliverables
- 套餐、订阅、配额、用量域模型与 API
- 计量管道与账单生成任务
- 配额拦截与超限提示机制
- 商业化计量一致性回归测试

## 5. Acceptance
- 可按套餐与配额限制系统使用
- 用量统计与账单结果可追溯
- 配额超限可实时拦截并留痕
- 跨租户账务数据隔离稳定

### 5.1 Quantitative Acceptance（量化验收）
- 同一 `tenant_id` 在任一时刻仅允许 `1` 条 `ACTIVE` 订阅（唯一约束）
- 用量事件采集具备幂等键：`tenant_id + meter_key + source_event_id` 唯一
- 配额策略命中顺序固定且可解释：`tenant_override > subscription_plan > system_default`
- 账单金额一致性：`invoice.total_amount = sum(invoice_lines.amount)`（结算前后校验一致）
- 账单关账后不可重算：`CLOSED` 状态禁止修改行项目，仅允许追加审计与调账记录
- 跨租户隔离校验通过：任一租户不可查询/修改他租户订阅、用量、账单

## 6. Exit Criteria
- `ruff`, `mypy`, `pytest`, `e2e` 全绿
- 计费与配额演示脚本可复跑

---

## 7. Priority Tuning (P0/P1/P2)

- P0（先做，阻塞商业化）：
  - `24-WP1` 套餐/订阅/配额最小闭环
  - `24-WP2` 用量采集与配额拦截最小链路
- P1（随后完成，形成可计费能力）：
  - `24-WP3` 账单生成与账期汇总 + 超限告警与审计增强
- P2（可延后到本阶段后半）：
  - 在 `24-WP2` 基础上补齐精细化计量口径与成本分摊优化
- 执行顺序：`P0 -> P1 -> P2 -> 24-WP4`

## 8. Execution Progress

- [x] 24-WP1 套餐订阅与配额最小闭环
- [x] 24-WP2 用量采集与配额拦截
- [x] 24-WP3 账单生成与治理增强
- [x] 24-WP4 验收关账

## 9. Implementation Contract（实现约束）

### 9.1 WP1（P0）套餐/订阅/配额最小链路必须包含
- 最小实体集合：`BillingPlanCatalog`、`BillingPlanQuota`、`TenantSubscription`、`TenantQuotaOverride`
- 订阅状态最小集合：`TRIAL`、`ACTIVE`、`SUSPENDED`、`EXPIRED`
- 所有订阅与配额实体必须带 `tenant_id` 作用域，并在读写链路强制租户边界
- 新增计费权限（建议 `billing.read`、`billing.write`）；历史高权限仅作过渡兼容，不作为长期边界

### 9.2 WP2（P0）用量采集与配额拦截约束
- 用量采集最小字段：`meter_key`、`quantity`、`occurred_at`、`source_event_id`、`meta`
- 必须支持事件幂等去重；重复 `source_event_id` 不得重复计量
- 配额判定顺序固定：`tenant_override > subscription_plan > system_default`
- 超限策略最小集合：`HARD_LIMIT`（拒绝）与 `SOFT_LIMIT`（放行+告警）
- 所有拦截与放行结果需落审计，并记录命中规则版本

### 9.3 WP3（P1）账单生成与账期汇总约束
- 账单状态最小集合：`DRAFT`、`ISSUED`、`CLOSED`、`VOID`
- 账单生成以账期窗口为边界（如月账期），同租户同账期禁止重复 `ISSUED/CLOSED`
- 仅 `DRAFT` 允许重算；`CLOSED` 仅允许调账记录，不允许改写历史行项目
- 账单生成、关账、调账需写审计动作并关联账期与租户

### 9.4 P2 边界
- 精细化计量口径与成本分摊仅在 `P0/P1` 闭环稳定后追加
- P2 不引入支付网关、税务发票、多币种复杂结算
- P2 不改变租户边界和审计强约束

### 9.5 迁移与一致性策略
- 新增计费能力按 `expand -> backfill/validate -> enforce` 三段迁移落地
- enforce 阶段补齐唯一约束、范围检查、复合外键（含 `tenant_id`）与必要索引
- 回填/校验阶段必须验证：幂等去重、账期唯一性、账单金额一致性

## 10. API Draft（WP 级接口草案）

### 10.1 WP1 - 套餐/订阅/配额治理
- `POST /api/billing/plans`
  - 创建套餐（`plan_code`、`display_name`、`billing_cycle`、`price`、`currency`）
- `GET /api/billing/plans`
  - 查询套餐目录（支持按 `plan_code`、`status` 过滤）
- `POST /api/billing/tenants/{tenant_id}/subscriptions`
  - 创建租户订阅（`plan_id`、`start_at`、`end_at`、`status`）
- `GET /api/billing/tenants/{tenant_id}/subscriptions`
  - 查询租户订阅历史/当前订阅
- `PUT /api/billing/tenants/{tenant_id}/quotas/overrides`
  - 设置租户级配额覆盖

### 10.2 WP2 - 用量采集与配额拦截
- `POST /api/billing/usage:ingest`
  - 上报用量事件（支持幂等键 `source_event_id`）
- `GET /api/billing/tenants/{tenant_id}/usage/summary`
  - 查询租户用量汇总（按 `meter_key`、时间窗）
- `POST /api/billing/tenants/{tenant_id}/quotas:check`
  - 显式配额校验（返回命中规则与是否允许）
- `GET /api/billing/tenants/{tenant_id}/quotas`
  - 查询生效配额快照（计划配额 + 覆盖配额）

### 10.3 WP3 - 账单生成与结算治理
- `POST /api/billing/invoices:generate`
  - 按租户/账期生成账单（或重跑 `DRAFT`）
- `GET /api/billing/tenants/{tenant_id}/invoices`
  - 查询账单列表（按账期与状态过滤）
- `GET /api/billing/invoices/{invoice_id}`
  - 查询账单详情与行项目
- `POST /api/billing/invoices/{invoice_id}:close`
  - 账单关账（`DRAFT/ISSUED -> CLOSED`）
- `POST /api/billing/invoices/{invoice_id}:void`
  - 废弃账单并保留审计轨迹

### 10.4 Permission & Audit（接口治理约束）
- 读接口使用 `billing.read`，写接口使用 `billing.write`
- 所有写接口必须写审计动作（`billing.plan.*`、`billing.subscription.*`、`billing.usage.*`、`billing.invoice.*`）
- 配额校验、超限拦截、账单关账必须记录 `tenant_id` 作用域与规则快照版本
