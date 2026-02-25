# Phase 10 - 一张图态势 v1

## 0. Basis
- Based on: `phases/phase-08-one-net-unified-flight-planning.md`
- Depends on: `phases/phase-09-flight-resource-asset-management.md`

## 1. Objective
交付可演示、可值守的“一张图”态势能力，统一呈现资源、任务、事件、告警与轨迹。

## 2. Scope
- 2D 地图态势页（基于现有轻量 UI 栈）
- 资源图层：无人机、资产、任务、事件、告警
- 实时轨迹与历史轨迹回放接口
- 视频窗口抽象（RTSP/WebRTC 接入占位，不做转码）

## 3. Out of Scope
- 任务中心统一工作流编排（Phase 11）
- 空域策略拦截与飞前合规校验（Phase 12）
- 实时视频转码与媒体中台建设

## 4. Deliverables
- 地图态势域模型与查询服务
- 一张图 API（图层、轨迹、回放、聚合态势）
- `/ui/command-center` 一张图增强版
- 演示脚本与回归测试（含跨租户边界）

## 5. Acceptance
- 可以在同一页面切换图层并查看实时态势
- 历史轨迹可按时间窗回放
- 告警/事件/任务叠加显示稳定
- 核心接口无跨租户越权

## 6. Exit Criteria
- `ruff`, `mypy`, `pytest`, `e2e` 全绿
- 一张图演示脚本可复跑

---

## 7. Priority Tuning (P0/P1/P2)

- P0（先做，阻塞后续阶段）：
  - `10-WP1` 地图态势聚合模型与接口骨架
  - `10-WP2` 实时轨迹与历史回放（先实现最小可回放链路）
- P1（随后完成，强化可用性）：
  - `10-WP3` 图层开关、回放控件、告警高亮
- P2（可延后到本阶段后半或下阶段联调）：
  - `10-WP3` 视频槽位高级适配细节（仅保留占位抽象即可）
- 执行顺序：`P0 -> P1 -> P2 -> 10-WP4`

## 8. Execution Progress

- [x] 10-WP1 地图态势聚合模型与接口骨架（已完成）
  - 图层聚合 DTO、查询入口、租户边界约束
  - 最小接口：`/api/map/overview`、`/api/map/layers/*`
- [x] 10-WP2 实时轨迹与历史回放（已完成）
  - 轨迹聚合服务（基于 telemetry）
  - 回放接口：按资源、时间窗、抽样粒度
  - 交付：
    - 新增模型：`MapLayer*`、`MapOverviewRead`、`MapTrackReplayRead`
    - 新增服务：`app/services/map_service.py`
    - 新增路由：`app/api/routers/map_router.py`
    - 新增接口：
      - `GET /api/map/overview`
      - `GET /api/map/layers/resources`
      - `GET /api/map/layers/tasks`
      - `GET /api/map/layers/alerts`
      - `GET /api/map/layers/events`
      - `GET /api/map/tracks/replay`
    - 测试：`tests/test_map.py`（图层聚合、轨迹回放、跨租户边界）
- [x] 10-WP3 一张图 UI 增强与视频槽位抽象（已完成）
  - 图层开关、轨迹回放控件、告警高亮
  - 视频窗口占位与接入适配抽象
  - 交付：
    - `app/web/templates/command_center.html` 增加图层开关、回放控件、告警面板、视频槽位占位面板
    - `app/web/static/command_center.js` 对接 `/api/map/*`，实现图层渲染、回放动画、告警高亮、视频槽位抽象渲染
    - 保留 `ws/dashboard` 统计流并与 map API 刷新协同
- [x] 10-WP4 验收关账（已完成）
  - 演示脚本：`infra/scripts/demo_phase10_one_map.py`
  - 报告：`logs/phase-10-unified-map-situation-v1.md.report.md`
  - 全门禁复验通过
  - 关账结果：
    - 质量门禁通过：`ruff`, `mypy`, `pytest`, `alembic`, `openapi_export`, `demo_e2e`, `verify_smoke`, `demo_phase10_one_map`
    - checkpoint 将进入 `phase-11-unified-task-center-workflow.md`（`READY`）
