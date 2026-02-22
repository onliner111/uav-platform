# 城市低空综合治理与应急指挥平台
# 系统架构说明书（V2.0）

- 文档版本：V2.0
- 架构范围：Phase 01-06 已实现能力
- 更新日期：2026-02-21

---

## 1. 架构目标与约束

### 1.1 目标

1. 支撑城管巡查高频业务
2. 支撑应急指挥场景展示与落地
3. 保证数据可追溯、流程可审计

### 1.2 约束

1. 单体架构（Monolith），禁止提前微服务拆分
2. 无前端构建流水线，采用 Jinja2 + 静态 JS
3. 容器化运行，统一通过 Docker Compose
4. 业务逻辑保持确定性，不将控制决策交给 LLM

---

## 2. 总体架构

```text
                 +-----------------------------+
                 |        Browser / API Client |
                 +--------------+--------------+
                                |
                                v
                     +----------+-----------+
                     |      FastAPI App     |
                     |  (Monolith, app/)    |
                     +----+-----+-----+-----+
                          |     |     |
                          |     |     +--------------------+
                          |     |                          |
                          v     v                          v
                    +-----+--+  +----------------+   +-----+------+
                    | Redis  |  | PostgreSQL     |   | Static UI  |
                    | state  |  | (PostGIS image)|   | Jinja2/JS  |
                    +--------+  +----------------+   +------------+
```

---

## 3. 分层设计

代码目录按职责分层：

1. `app/api`：HTTP/WS 入口、鉴权、路由编排
2. `app/services`：业务用例与流程编排
3. `app/domain`：领域模型、状态机、权限常量
4. `app/infra`：数据库、审计中间件、事件总线、OpenAPI 导出
5. `app/adapters`：无人机适配器插件（`FAKE`/`DJI`/`MAVLINK`）
6. `app/web`：Jinja2 页面与静态资源

---

## 4. 核心模块

### 4.1 身份与权限模块（Identity/RBAC）

- 租户、用户、角色、权限、角色绑定、权限绑定
- JWT 鉴权
- 权限守卫 `require_perm(...)`

### 4.2 巡查模块（Inspection）

- 模板与检查项管理
- 巡查任务管理
- 观测点采集
- 报告导出（HTML）
- UI：`/ui/inspection`、`/ui/inspection/tasks/{task_id}`

### 4.3 问题闭环模块（Defect）

- 由观测点生成问题单
- 指派与状态流转
- 操作历史追踪
- 统计闭环率
- UI：`/ui/defects`

### 4.4 应急模块（Incident/Emergency）

- 事件创建
- 一键生成应急任务（自动关联 `mission_id`）
- UI：`/ui/emergency`

### 4.5 指挥中心模块（Dashboard）

- 聚合统计 API
- 实时 WebSocket 推送
- 地图观测点实时展示
- UI：`/ui/command-center`

### 4.6 合规模块（Approval/Audit）

- 审批记录
- 审计导出
- 关键写操作审计日志落库（`audit_logs`）

### 4.7 报表模块（Reporting）

- 总览统计
- 闭环率统计
- 设备利用率统计
- 报表导出（PDF）

---

## 5. 数据架构

### 5.1 多租户隔离

所有核心业务表包含 `tenant_id`，查询侧按 `tenant_id` 过滤实现逻辑隔离。

### 5.2 核心实体（节选）

1. 身份与权限：`tenants/users/roles/permissions`
2. 巡查：`inspection_templates`、`inspection_tasks`、`inspection_observations`
3. 问题：`defects`、`defect_actions`
4. 应急：`incidents`
5. 合规：`approval_records`
6. 审计：`audit_logs`
7. 事件：`events`

---

## 6. 关键流程时序

### 6.1 巡查主流程

```text
模板创建 -> 任务创建 -> 观测点写入 -> 地图展示 -> 导出报告
```

### 6.2 问题闭环流程

```text
观测点 -> 生成问题单 -> 指派 -> 处理 -> 复核 -> 关闭
```

状态机：

`OPEN -> ASSIGNED -> IN_PROGRESS -> FIXED -> VERIFIED -> CLOSED`

### 6.3 应急流程

```text
事件创建 -> 选择区域 -> 一键创建应急任务 -> 进入调度与监看
```

---

## 7. 事件与审计机制

### 7.1 事件机制

- 业务状态变更通过 `event_bus` 发布到 `events` 表
- 用于追踪关键生命周期，如任务创建、状态变化、审批等

### 7.2 审计机制

- `AuditMiddleware` 对写请求记录审计日志
- 审计字段包括：租户、操作人、动作、资源、HTTP 方法、状态码、时间

---

## 8. 实时能力设计

### 8.1 遥测通道

- 遥测写入 Redis 最新状态
- 支持 WebSocket 推送无人机实时数据

### 8.2 指挥中心实时通道

- `WS /ws/dashboard` 周期推送统计与地图点
- 前端按流式数据增量刷新

---

## 9. 部署架构

部署单元：

1. `app`：主业务服务
2. `db`：PostgreSQL（PostGIS）
3. `redis`：状态缓存
4. `app-tools`：脚本执行与验证

编排方式：

- `infra/docker-compose.yml`
- `Makefile` 封装 lint/typecheck/test/e2e

---

## 10. 安全设计

1. JWT 身份认证
2. 细粒度权限控制（接口级）
3. 租户数据隔离
4. 关键行为审计
5. 导出动作可追踪

---

## 11. 可扩展性设计

### 11.1 适配器扩展

新增无人机厂商时，只需在 `app/adapters` 增加实现并在服务中注册。

### 11.2 业务扩展

新增业务优先通过：

1. 新增领域模型 + 迁移
2. 新增服务层用例
3. 新增 API 路由与权限
4. 新增审计与事件

---

## 12. 已知限制与演进建议

已知限制：

1. 几何字段当前使用文本表达，未启用复杂空间计算
2. Dashboard 推送采用轮询式推送，不是事件驱动聚合总线
3. 导出文件存储在本地文件系统，需外部归档策略

演进建议：

1. 接入对象存储管理导出文件生命周期
2. 增加监控告警指标（延迟、吞吐、错误率）
3. 在规模增长后评估分层拆分与异步任务队列


---

## 13. �ӿ��嵥��¼

��ϸ�ӿ���μ���doc/API_Appendix_V2.0.md��

�ܹ�������ӿ�����Ӧ�Ըø�¼��Ϊ��ǰʵ�ֻ��ߡ�
