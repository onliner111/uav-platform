# Phase 23 - AI 任务化与模型治理 v2

## 0. Basis
- Based on: `111.md`
- Depends on: `phases/phase-22-alert-oncall-notification-v2.md`

## 1. Objective
把 AI 从单次能力升级为可治理、可灰度、可回滚的持续运营能力中心。

## 2. Scope
- 模型注册与版本管理
- 阈值配置与灰度发布
- 准实时任务调度增强
- 评估指标、回滚与对比分析
- 人审兜底流程与审计联动强化

## 3. Out of Scope
- 自研训练平台与全生命周期 MLOps
- AI 实时控制飞行链路

## 4. Deliverables
- 模型目录与版本治理模型/API
- 灰度发布与阈值策略能力
- 评估与回滚流程
- AI 治理回归测试与演示脚本

## 5. Acceptance
- 模型版本可追踪与回滚
- 灰度发布可按策略生效
- 评估指标可用于版本对比
- 人审兜底始终有效且可审计

### 5.1 Quantitative Acceptance（量化验收）
- 同一 `tenant_id + model_key` 仅允许 `1` 个 `STABLE` 版本（唯一约束）
- 灰度策略权重总和必须为 `100`，任一灰度版本权重范围 `1..99`
- 回滚操作触发后，新的 run 选型应在 `1` 次策略刷新周期内切回目标稳定版本
- 评估指标最小集合可查询：`success_rate`、`review_override_rate`、`p95_latency_ms`
- 人审兜底不弱化：`control_allowed=false` 保持强约束，默认 `PENDING_REVIEW`

## 6. Exit Criteria
- `ruff`, `mypy`, `pytest`, `e2e` 全绿
- AI 模型治理演示脚本可复跑

---

## 7. Priority Tuning (P0/P1/P2)

- P0（先做，阻塞可控上线）：
  - `23-WP1` 模型注册与版本治理最小链路
  - `23-WP2` 阈值与灰度发布最小链路
- P1（随后完成，形成持续运营能力）：
  - `23-WP3` 评估与回滚机制 + 准实时调度增强与审计联动
- P2（可延后到本阶段后半）：
  - 在 `23-WP2` 基础上补齐自动化策略推荐与智能调参
- 执行顺序：`P0 -> P1 -> P2 -> 23-WP4`

## 8. Execution Progress

- [x] 23-WP1 模型注册与版本治理
- [x] 23-WP2 阈值与灰度发布
- [x] 23-WP3 评估回滚与调度增强
- [x] 23-WP4 验收关账

## 9. Implementation Contract（实现约束）

### 9.1 WP1（P0）最小链路必须包含
- 模型治理实体最小集合：`model_catalog`、`model_version`、`model_rollout_policy`
- 版本状态最小集合：`DRAFT`、`CANARY`、`STABLE`、`DEPRECATED`
- `ai_analysis_jobs` 需绑定治理版本（如 `model_version_id`），但保留运行时快照字段用于证据链追溯
- 新增 AI 治理权限（建议 `ai.read`、`ai.write`）；现网 `reporting.*` 仅作过渡兼容，不作为长期治理权限边界

### 9.2 WP2（P0）阈值与灰度发布约束
- 策略解析顺序固定：`人工强制指定 > job 局部策略 > 模型默认策略`
- 灰度分流先实现“按 job 的权重分配”，不引入跨服务流量网关
- 每次 run 必须落库“命中版本 + 命中策略 + 阈值快照”，并写入证据链

### 9.3 WP3（P1）评估、回滚、准实时调度约束
- 准实时调度采用“外部 cron 驱动 + 平台显式触发接口”模式，避免在本阶段引入常驻调度器
- 调度执行需具备幂等窗口键（同窗口重复触发不重复执行）
- 回滚以“策略切换”为主，不重写历史 run/output；历史仅追加审计与回滚记录
- 评估先聚焦线上可观测指标，不引入离线训练评测平台

### 9.4 P2 边界
- 自动化策略推荐与智能调参仅在 `P0/P1` 闭环稳定后追加
- P2 不得改变 `human-in-the-loop` 强约束与租户边界判定

### 9.5 迁移与一致性策略
- 所有新增治理能力按 `expand -> backfill/validate -> enforce` 三段迁移落地
- enforce 阶段补齐枚举检查、范围检查、唯一约束、复合外键（含租户键）与必要索引
- 回填/校验阶段必须显式校验历史数据与策略快照可解释性

## 10. API Draft（WP 级接口草案）

### 10.1 WP1 - 模型注册与版本治理
- `POST /api/ai/models`
  - 创建模型目录（`model_key`、`provider`、`display_name`、`description`）
- `GET /api/ai/models`
  - 列出模型目录（支持按 `model_key`、`provider` 过滤）
- `POST /api/ai/models/{model_id}/versions`
  - 创建模型版本（`version`、`status`、`artifact_ref`、`threshold_defaults`）
- `GET /api/ai/models/{model_id}/versions`
  - 列出版本（按 `status`、`created_at` 排序/过滤）
- `POST /api/ai/models/{model_id}/versions/{version_id}:promote`
  - 版本状态流转（`DRAFT -> CANARY -> STABLE`）

### 10.2 WP2 - 阈值与灰度发布
- `PUT /api/ai/models/{model_id}/rollout-policy`
  - 更新灰度策略（版本权重、默认阈值、有效期）
- `GET /api/ai/models/{model_id}/rollout-policy`
  - 读取当前策略快照
- `POST /api/ai/jobs/{job_id}:bind-model-version`
  - 为 job 绑定治理版本（允许覆盖默认策略）

### 10.3 WP3 - 评估、回滚、准实时调度
- `POST /api/ai/evaluations:recompute`
  - 触发评估聚合（时间窗、模型版本、job 维度）
- `GET /api/ai/evaluations/compare`
  - 版本对比查询（最小指标集）
- `POST /api/ai/models/{model_id}/rollout-policy:rollback`
  - 回滚到指定稳定版本并写审计
- `POST /api/ai/jobs:schedule-tick`
  - 准实时调度触发入口（支持幂等窗口键）

### 10.4 Permission & Audit（接口治理约束）
- 读接口使用 `ai.read`，写接口使用 `ai.write`（保留 `reporting.*` 兼容窗口）
- 所有写接口必须写审计动作（`ai.model.*`、`ai.rollout.*`、`ai.evaluation.*`、`ai.schedule.*`）
- 评估、回滚、调度接口必须记录 `tenant_id` 作用域与策略快照版本
