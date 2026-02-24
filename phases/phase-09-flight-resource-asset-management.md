# Phase 09 - 飞行资源与资产管理

## 0. Basis
- Based on: `phases/phase-08-one-net-unified-flight-planning.md`
- Depends on: `phases/phase-08d-integration-acceptance.md`

## 1. Objective
将无人机、载荷、电池、遥控器、机巢及维护工单纳入统一资源管理，形成“可调度、可维护、可追溯”的资产基线。

## 2. Scope
- 资产台账模型与生命周期（注册、绑定、退役）
- 资源可用性与健康度模型
- 维护工单与历史记录
- 区域资源池查询（回答“当前哪里有什么可飞资源”）

## 3. Out of Scope
- 地图多图层态势与轨迹回放（Phase 10）
- 任务中心统一工作流（Phase 11）

## 4. Deliverables
- 资产域数据模型与迁移链路
- 资源管理 API（资产、可用性、维护）
- 资源池查询接口与最小演示链路
- 回归测试与运维文档（资产与维护操作手册）

## 5. Acceptance
- 资产生命周期可完整演示（注册 -> 绑定 -> 维护 -> 退役）
- 资源池查询可按租户与区域返回可用资源
- 维护历史可查询且关键动作可审计
- 核心路径无跨租户越权

## 6. Exit Criteria
- `ruff`, `mypy`, `pytest`, `e2e` 全绿
- Phase 10 所需资源基座可复用

---

## 7. Execution Progress

- [x] 09-WP1 资产台账模型与迁移（已完成）
  - 资产实体：无人机/载荷/电池/遥控器/机巢
  - 生命周期字段：注册/绑定/退役
  - 迁移与最小回归测试
  - 交付：
    - `assets` 资产台账模型（`AssetType` + `AssetLifecycleStatus`）
    - 迁移链路 `202602240035/036/037`（expand/backfill-validate/enforce）
    - 最小 API：创建/列表/详情/绑定/退役（`/api/assets`）
    - 测试：`tests/test_asset.py`（生命周期、筛选、事件、跨租户边界）
- [x] 09-WP2 资源可用性与健康度（已完成）
  - 可用状态与健康指标模型
  - 基础查询与筛选 API
  - 交付：
    - 资产可用性/健康度模型：`AssetAvailabilityStatus` + `AssetHealthStatus`
    - 迁移链路 `202602240038/039/040`（expand/backfill-validate/enforce）
    - API：
      - `POST /api/assets/{asset_id}/availability`
      - `POST /api/assets/{asset_id}/health`
      - `GET /api/assets/pool`（按可用性/健康度/区域/类型筛选）
    - 测试：`tests/test_asset.py` 新增 WP2 覆盖（可用性转换、资源池查询、跨租户边界、退役资产冲突）
- [x] 09-WP3 维护工单与历史（已完成）
  - 工单创建/流转/关闭
  - 关键维护动作审计链路
  - 交付：
    - 模型：`AssetMaintenanceWorkOrder` + `AssetMaintenanceHistory`
    - 迁移链路 `202602240041/042/043`（expand/backfill-validate/enforce）
    - API：
      - `POST /api/assets/maintenance/workorders`
      - `GET /api/assets/maintenance/workorders`
      - `GET /api/assets/maintenance/workorders/{workorder_id}`
      - `POST /api/assets/maintenance/workorders/{workorder_id}/transition`
      - `POST /api/assets/maintenance/workorders/{workorder_id}/close`
      - `GET /api/assets/maintenance/workorders/{workorder_id}/history`
    - 审计：关键动作 `create/transition/close/history.list` 显式写入审计 action
    - 测试：`tests/test_asset_maintenance.py`（流转、历史、冲突、跨租户、事件）
- [x] 09-WP4 区域资源池查询与验收关账（已完成）
  - 区域维度资源池汇总查询
  - 全门禁复验与 Phase 报告
  - 交付：
    - 区域资源池聚合查询：`GET /api/assets/pool/summary`
    - 验收演示脚本：`infra/scripts/demo_phase09_resource_pool_maintenance.py`
    - 关账报告：`logs/phase-09-flight-resource-asset-management.md.report.md`
    - 全门禁复验通过（`ruff/mypy/pytest/alembic/openapi/demo_e2e/verify_smoke/verify_phase08/demo_phase09`）
