## Responsibility Header
- Role: Execution playbook (SSOT for how delivery is executed).
- Includes: operational commands, validation flow, and implementation workflow constraints.
- Excludes: phase definitions and phase acceptance content (owned by `phases/phase-*.md`) and product milestone strategy (owned by `ROADMAP.md`).

# CODEX_PLAN.md — 一网统飞（单体 Monolith + 插件式 Adapter + 多租户）零预装依赖版

> 读者：Codex（自动编码代理）
> 目标：尽量少人工干预，从零到端到端演示可跑通。
> 运行要求：**宿主机只需要 Docker + Docker Compose**。

---

## A. Zero-Setup Mode（硬性）
本项目必须在“零预装依赖”模式下可运行：
- 宿主机不要求预装：Python / Node / Postgres / Redis / Kafka / MQTT / OpenAPI 工具
- 一键启动必须可用：
  - `docker compose up --build`
  - 或 `make up`
- 所有工具（lint/test/openapi/e2e）必须在容器内运行（通过 compose 或 docker run）

---

## B. Codex 运行指令（必须照做）
### B.1 一次只做一个 Phase
每次只实现一个 Phase。完成后必须提交：
1) 本 Phase 完成清单（逐条勾选）
2) 新增/变更 API 列表（路径、权限）
3) 如何验证（命令）
4) 测试结果（全绿）
5) 关键设计决策（<=10条）

### B.2 质量门禁（硬性）
每次提交前必须在容器内跑并通过：
- `make lint`
- `make typecheck`
- `make test`
- Phase 引入 e2e 后：`make e2e`

### B.3 禁止跑偏
- 禁止在业务层写 DJI/MAVLink 细节：必须在 Adapter 插件内封装
- 禁止让 LLM 参与实时控制闭环：只做任务/监管/告警/处置建议与命令下发

---

## C. 总体架构（单体 + 插件式）
### C.1 单体服务：uav_app（一个 FastAPI）
一个进程/一个服务，内部按模块分层：
- api/（路由）
- domain/（实体与状态机）
- services/（业务用例）
- adapters/（插件：mavlink、dji、fake）
- infra/（DB/Redis/事件总线/任务队列）
- web/（可选最小前端：Swagger 已足够）

### C.2 Adapter 插件接口（关键）
业务层只调用统一接口，不关心 DJI/MAVLink：
- connect/disconnect
- start_stream(drone_id) 产出 TelemetryNormalized 事件
- send_command(drone_id, Command) -> Ack
- upload_mission_plan(drone_id, MissionPlan)
- start_mission / abort / rth / land / hold

---

## D. 技术栈（固定、尽量轻量）
- Python 3.11 + FastAPI
- PostgreSQL + PostGIS（用 docker）
- Redis（用 docker；存最新态势/心跳）
- 事件总线（优先轻量内置）：
  - MVP：进程内 event bus + events 表存档（强烈建议）
  - 可选：后续接 Kafka，但不作为必需依赖
- MQTT broker（可选；MVP 可用 HTTP ingest + fake adapter）
- pytest + httpx
- ruff + mypy
- Alembic 迁移
- OpenAPI artifacts：使用 dockerized openapi-generator 生成 client/Postman（至少一种，推荐两种）

---

## E. 仓库结构（必须按此创建）
uav-platform/
  app/
    main.py
    api/
      deps.py
      routers/
        identity.py
        registry.py
        mission.py
        telemetry.py
        command.py
        alert.py
    domain/
      models.py          # SQLModel + Pydantic domain models
      state_machine.py   # Mission 状态机
      permissions.py
    services/
      identity_service.py
      registry_service.py
      mission_service.py
      telemetry_service.py
      command_service.py
      alert_service.py
    adapters/
      base.py            # Adapter 接口定义
      fake_adapter.py
      mavlink_adapter.py
      dji_adapter.py     # 骨架/占位
    infra/
      db.py              # session/engine
      migrate.py         # migrate helper
      auth.py            # jwt
      audit.py
      tenant.py
      events.py          # event store + in-proc bus
      redis_state.py
  infra/
    docker-compose.yml
    migrations/
    scripts/
      demo_e2e.py
      verify_smoke.py
  openapi/
    clients/
    postman/
  Dockerfile
  requirements.txt
  requirements-dev.txt
  Makefile
  .env.example
  CODEX_PLAN.md

---

## F. 统一数据契约（必须实现）
### F.1 EventEnvelope
- event_id, event_type, tenant_id, ts, actor_id?, correlation_id?, payload

### F.2 TelemetryNormalized
- tenant_id, drone_id, ts
- position {lat, lon, alt_m}
- battery {percent, voltage?, current?}?
- link {rssi?, latency_ms?}?
- mode string
- health dict

### F.3 Command
- tenant_id, command_id, drone_id, ts
- type: [RTH, LAND, HOLD, GOTO, START_MISSION, ABORT_MISSION, PAUSE, RESUME]
- params dict
- idempotency_key string
- expect_ack bool

### F.4 MissionPlan
- type: [AREA_GRID, ROUTE_WAYPOINTS, POINT_TASK]
- payload dict（GeoJSON/waypoints/point）
- constraints dict（max_alt, speed, time_window, emergency_fastlane, priority, no_fly_check...）

---

## G. 数据库（最小表，必须）
多租户与权限：
- tenants, users, roles, permissions, user_roles, role_permissions
- audit_logs

设备：
- drones (vendor: DJI|MAVLINK|FAKE), drone_credentials

任务：
- missions, approvals, mission_runs

地理（PostGIS）：
- geofences (geometry), no_fly_zones (optional)

事件存档：
- events（强烈建议强制）

---

## H. API 与权限（最小要求）
- 所有路由必须：
  - 解析 JWT 得到 tenant_id/user_id
  - RBAC 检查（require_perm）
  - 自动审计（写操作）
- 健康检查：
  - GET /healthz
  - GET /readyz（检查 DB/Redis）

---

## I. 分阶段工作计划（严格顺序、低人工干预）

### Phase 0 — 工程骨架 + 全容器化工具链（P0）
交付：
- Dockerfile（单体服务）
- docker-compose（Postgres+PostGIS、Redis、app）
- Makefile（所有命令在容器内执行）：
  - make up/down/logs
  - make lint/typecheck/test
  - make migrate
  - make openapi
- libs/infra 基础能力：
  - jwt、tenant、rbac、audit、db、alembic
  - events：events 表 + in-proc bus（publish/subscribe）
- CI：用 docker compose 启动后运行 lint/test/migrate

验收：
- `docker compose up --build` 能启动并 /healthz ok
- `make lint typecheck test` 全绿（在容器内）

### Phase 1 — Identity（P0）
- tenants/users/roles/permissions CRUD
- dev 登录签 JWT
- 测试：隔离 + 权限拒绝

### Phase 2 — Registry（P0）
- drones CRUD（vendor/capabilities）
- 测试：隔离
- 事件：drone.registered/updated

### Phase 3 — Mission（P0）
- missions CRUD + approvals
- 状态机 + emergency_fastlane（授权信息强制）
- 测试：非法跳转 409 + 权限 + fastlane
- 事件：mission.*

### Phase 4 — Telemetry（P0）
- ingest：HTTP `POST /telemetry/ingest`
- Redis 最新态势：state:{tenant}:{drone}
- WebSocket：/ws/drones（推送态势）
- 事件：telemetry.normalized
- 测试：写入/查询/WS

### Phase 5 — Command（P0）
- 发命令 API（幂等）
- Adapter 执行 + ack
- 超时与重试（最小实现：超时标记 TIMEOUT）
- 事件：command.*
- 测试：幂等 + ack + timeout

### Phase 6 — Adapters（P1）
#### 6.1 FakeAdapter（强制）
- 模拟多架无人机发送 telemetry（位置、电量递减）
- 可响应 command（立即 ack）
- 支持触发：低电/失联/越界

#### 6.2 MavlinkAdapter（最小闭环）
- 使用 pymavlink 连接 UDP/TCP（支持 SITL）
- 订阅 HEARTBEAT/GLOBAL_POSITION_INT/SYS_STATUS -> TelemetryNormalized
- 支持 RTL/LOITER/LAND（命令映射）
- 若无真实环境：提供“模拟模式”保持 e2e 可跑

#### 6.3 DJIAdapter（骨架）
- 接口占位 + fake 模拟，确保业务可用

### Phase 7 — Alert（P1）
- 规则：低电/失联/越界（越界用 PostGIS）
- API：告警列表/ack/close
- 事件：alert.*
- 测试：输入 telemetry -> 产生告警

### Phase 8 — OpenAPI 回归 artifacts + e2e（P0 贯穿，最终强制）
交付：
- 导出 openapi.json（运行时拉取或构建时）
- dockerized openapi-generator 生成：
  - Python client（推荐）
  - Postman collection（推荐）
- CI 中运行：
  - client 冒烟调用 或 Newman 跑 collection

### Phase 9 — 端到端脚本（强制）
- infra/scripts/demo_e2e.py：
  1) 创建 tenant/user -> JWT
  2) 注册 drone（FAKE）
  3) 启动 fake adapter（容器内或同进程）
  4) 创建巡检任务并审批
  5) 下发 RTH 命令并 ack
  6) 触发低电告警并查询
- infra/scripts/verify_smoke.py：
  - 验证关键 endpoints（healthz/CRUD/ws）
- Makefile：`make e2e` 一键：
  - compose up -d
  - migrate
  - openapi
  - demo + smoke
  - 失败返回非零

---

## J. Makefile（必须：全部在容器内执行）
必须提供目标：
- up/down/logs
- lint/typecheck/test
- migrate
- openapi（使用 docker run openapitools/openapi-generator-cli）
- e2e

禁止要求宿主机安装 python/node/openapi 工具。

---

## K. CI（必须）
- 使用 docker compose 启动依赖
- 在容器内执行：
  - lint/typecheck/test
  - migrate
  - openapi
  - e2e
- 失败阻止合并

---

## L. 最终验收
- `docker compose up --build` 后 /healthz ok
- Swagger 可用
- `make e2e` 稳定通过
- 多租户隔离、权限、状态机、幂等、告警均有测试覆盖
- FakeAdapter 端到端通过
- OpenAPI artifacts 可回归（client 或 Postman）
