# 城市低空综合治理与应急指挥平台
# 用户使用手册（V3.0）

- 文档版本：V3.0
- 适用系统版本：阶段 `phase-01` 至 `phase-39` 已完成版本
- 更新日期：2026-03-02

---

## 1. 系统概述

本平台用于城市低空巡查与应急指挥，覆盖以下业务闭环：

1. 巡查模板与巡查任务管理
2. 巡查结果采集与地图展示
3. 问题单（缺陷）闭环流转
4. 应急事件一键创建任务
5. 角色化工作台与一张图值守
6. 空域合规与飞前检查
7. 通知协同与统一待办
8. 业务闭环、成果复核与领导汇报
9. 上线保障、培训引导与版本运营
10. AI 助手分析、治理能力与开放接入

### 1.1 建议谁看这份文档

本手册主要面向：

- 指挥员
- 调度员
- 现场执行人员
- 合规人员
- 需要了解日常使用路径的业务用户

如果你主要负责：

- 租户、角色、上线、交接：请优先看管理员手册
- 接口联调或系统集成：请优先看 API 附录
- 不确定该看哪份：请先看 `docs/文档导航_V3.0.md`

---

## 2. 角色与权限

系统基于租户隔离与 RBAC 权限控制。典型权限包括：

- `inspection:read` / `inspection:write`
- `defect.read` / `defect.write`
- `incident.read` / `incident.write`
- `dashboard.read`
- `approval.read` / `approval.write`
- `reporting.read` / `reporting.write`

说明：
- 所有业务数据都带 `tenant_id`，不同租户间数据隔离。
- 管理员可通过身份模块为角色绑定权限并分配给用户。

---

## 3. 快速开始

### 3.1 启动服务

```powershell
docker --context default compose -f infra/docker-compose.yml up -d --build app app-tools db redis
docker --context default compose -f infra/docker-compose.yml run --rm app alembic upgrade head
```

服务默认地址：
- API：`http://localhost:8000`
- OpenAPI：`http://localhost:8000/docs`

### 3.2 初始化租户管理员

1. 创建租户：`POST /api/identity/tenants`
2. 初始化管理员：`POST /api/identity/bootstrap-admin`
3. 登录获取令牌：`POST /api/identity/dev-login`

成功登录后得到 `access_token`（JWT）。

### 3.3 鉴权方式

- API 调用：`Authorization: Bearer <access_token>`
- 推荐 UI 入口：先访问 `/ui/login`，登录后使用会话进入控制台
- 兼容方式：仍支持通过查询参数传入 token，例如：
  - `/ui/console?token=<access_token>`
  - `/ui/command-center?token=<access_token>`

### 3.4 推荐使用路径

1. 登录后先进入 `/ui/console`
2. 从角色工作台进入高频业务页面
3. 日常业务优先使用主导航
4. 低频管理员能力使用“管理员专项”入口

---

## 4. 角色工作台与首页导航

### 4.1 工作台首页

页面入口：

`GET /ui/console`

首页会按当前账号权限显示不同角色入口，常见角色包括：

- 指挥工作台
- 调度工作台
- 现场执行工作台
- 合规工作台
- 领导视图

说明：
- 每个角色入口只展示与该职责强相关的模块。
- 首页同时提供“常用业务入口”和“管理员专项入口”。

### 4.2 推荐导航顺序

1. 指挥 / 调度角色：先看工作台，再进入指挥中心或通知协同中心
2. 现场角色：先看巡检任务，再处理缺陷闭环
3. 合规角色：先看审批与通知，再进入业务闭环与汇报

---

## 5. 巡查业务操作（Inspection）

### 5.1 创建巡查模板

1. 调用 `POST /api/inspection/templates`
2. 为模板添加检查项：`POST /api/inspection/templates/{id}/items`

常见检查项示例：
- 占道经营
- 垃圾堆放
- 违规摆摊

### 5.2 创建巡查任务

调用 `POST /api/inspection/tasks`，填写：
- 任务名称
- 模板 ID
- 巡查区域（`area_geom`，文本几何表示）
- 状态（如 `SCHEDULED`）

### 5.3 上报巡查观测点

调用 `POST /api/inspection/tasks/{task_id}/observations`，填写：
- 经纬度、高度
- 检查项编码
- 严重等级
- 备注、置信度、媒体链接（可选）

### 5.4 巡查地图查看与导出

- 任务列表页面：`GET /ui/inspection?token=<token>`
- 任务地图详情：`GET /ui/inspection/tasks/{task_id}?token=<token>`
- 导出 HTML 报告：`POST /api/inspection/tasks/{task_id}/export?format=html`

---

## 6. 问题闭环操作（Defect）

### 6.1 由观测点生成问题单

`POST /api/defects/from-observation/{observation_id}`

### 6.2 指派责任人

`POST /api/defects/{id}/assign`

### 6.3 状态流转

`POST /api/defects/{id}/status`

标准流转顺序：

`OPEN -> ASSIGNED -> IN_PROGRESS -> FIXED -> VERIFIED -> CLOSED`

### 6.4 统计与列表

- 问题列表：`GET /api/defects`
- 问题详情（含操作历史）：`GET /api/defects/{id}`
- 闭环统计：`GET /api/defects/stats`
- 管理页面：`GET /ui/defects?token=<token>`

---

## 7. 应急处置操作（Emergency）

### 7.1 创建应急事件

`POST /api/incidents`

输入：
- 事件标题
- 事件等级（如 `HIGH`）
- 事件位置（`location_geom`）

### 7.2 一键生成应急任务

`POST /api/incidents/{id}/create-task`

系统将自动：
1. 生成应急关联任务（高优先级）
2. 关联 `mission_id`
3. 更新事件状态

### 7.3 页面入口

`GET /ui/emergency?token=<token>`

---

## 8. 指挥中心使用（Command Center）

页面入口：

`GET /ui/command-center?token=<token>`

### 8.1 页面形态

当前指挥中心为“一张图值守模式”，支持：

- 值守模式
- 领导模式
- 演示模式

并提供：

- 图层开关
- 当前模式摘要
- 当前焦点对象
- 事件时间轴

### 8.2 大屏展示指标

- 在线设备数
- 今日巡查次数
- 问题总数
- 实时告警数
- 地图观测点

### 8.3 数据接口

- 统计接口：`GET /api/dashboard/stats`
- WebSocket：`/ws/dashboard?token=<token>`

---

## 9. 合规与审计（Compliance）

### 9.1 空域与飞前检查

- 空域规则区：
  - `POST /api/compliance/zones`
  - `GET /api/compliance/zones`
- 飞前模板：
  - `POST /api/compliance/preflight/templates`
  - `GET /api/compliance/preflight/templates`
- 任务飞前检查：
  - `POST /api/compliance/missions/{mission_id}/preflight/init`
  - `GET /api/compliance/missions/{mission_id}/preflight`
  - `POST /api/compliance/missions/{mission_id}/preflight/check-item`

### 9.2 审批记录

- 新增审批：`POST /api/approvals`
- 查询审批：`GET /api/approvals`

### 9.3 审计导出

`GET /api/approvals/audit-export`

导出文件位于：`logs/exports/`

---

## 10. 通知协同中心（Alerts / Collaboration）

页面入口：

`GET /ui/alerts`

当前页面已从传统“告警中心”升级为“通知协同中心”，包含：

- 消息中心与待办中心
- 统一待办视图
- 告警处理与催办
- 通知渠道与发送策略
- 回执、催办与升级跟踪

使用建议：

1. 值班人员先处理高优先消息与待办
2. 再进入具体告警处置或审批流转
3. 需要复盘时查看升级与回执记录

---

## 11. 业务闭环与汇报（Reporting）

页面入口：

`GET /ui/reports`

当前页面已从传统“报表中心”升级为“业务闭环与汇报”，包含：

- 问题闭环看板
- 成果审核与复核工作台
- 典型案例与专题视图
- 领导汇报与专题分析

### 11.1 报表接口

- 总览：`GET /api/reporting/overview`
- 闭环率：`GET /api/reporting/closure-rate`
- 设备利用率：`GET /api/reporting/device-utilization`

### 11.2 导出报告

`POST /api/reporting/export`

支持参数：
- `task_id`：按任务导出
- `from_ts` / `to_ts`：按时间范围导出
- `topic`：按专题导出

导出文件位于：`logs/exports/`（PDF）。

### 11.3 KPI 统计与治理报表

- 重算 KPI 快照：`POST /api/kpi/snapshots/recompute`
- 查询快照：`GET /api/kpi/snapshots`
- 查询最新快照：`GET /api/kpi/snapshots/latest`
- 热力图数据：`GET /api/kpi/heatmap`
- 导出治理报表：`POST /api/kpi/governance/export`

---

## 12. 开通、上线与版本运营（Platform）

页面入口：

`GET /ui/platform`

当前页面已从“平台治理”升级为“上线保障与版本运营台”，主要用于：

- 租户开通向导
- 标准配置包与模板中心
- 模式切换与交付交接
- 上线检查清单与巡检面板
- 内置帮助中心与培训模式
- 发布说明与升级引导
- 功能开关与灰度启用

普通业务用户建议：

1. 仅在管理员指导下使用该页面
2. 优先按页面向导执行，不直接使用高级治理区
3. 生产切换前先完成上线检查清单

---

## 13. 租户级数据导出与清理（Tenant Export / Purge）

说明：本能力用于租户级备份与安全清理，默认仅管理员使用。

### 13.1 租户导出

1. 触发导出：`POST /api/tenants/{tenant_id}/export?include_zip=true`
2. 查询状态：`GET /api/tenants/{tenant_id}/export/{export_id}`
3. 下载压缩包：`GET /api/tenants/{tenant_id}/export/{export_id}/download`

导出目录：
- `logs/exports/<tenant_id>/<export_id>/manifest.json`
- `logs/exports/<tenant_id>/<export_id>/tables/*.jsonl`

### 13.2 清理 dry-run（不删除）

接口：`POST /api/tenants/{tenant_id}/purge:dry_run`

返回内容包括：
- `plan`：按依赖顺序的删除计划
- `counts`：每表行数
- `estimated_rows`：预计删除总行数
- `confirm_token`：执行清理时需要使用

### 13.3 执行清理（真删）

接口：`POST /api/tenants/{tenant_id}/purge`

请求体示例：

```json
{
  "dry_run_id": "<dry_run_id>",
  "confirm_token": "<confirm_token>",
  "mode": "hard"
}
```

说明：
- 必须先完成 dry-run。
- `confirm_token` 与 `confirm_phrase` 至少提供一个。
- 固定确认短语：`I_UNDERSTAND_THIS_WILL_DELETE_TENANT_DATA`。

### 13.4 查询清理结果

接口：`GET /api/tenants/{tenant_id}/purge/{purge_id}`

清理报告目录：
- `logs/purge/<tenant_id>/<purge_id>/report.json`

---

## 14. 成果与告警闭环（Outcomes + Alert）

### 14.1 成果目录

- 原始数据目录：
  - `POST /api/outcomes/raw`
  - `GET /api/outcomes/raw`
- 成果记录：
  - `POST /api/outcomes/records`
  - `GET /api/outcomes/records`
  - `POST /api/outcomes/records/from-observation/{observation_id}`
  - `PATCH /api/outcomes/records/{outcome_id}/status`

### 14.2 告警处置闭环

- 路由规则管理：
  - `POST /api/alert/routing-rules`
  - `GET /api/alert/routing-rules`
- 告警处置：
  - `POST /api/alert/alerts/{alert_id}/actions`
  - `GET /api/alert/alerts/{alert_id}/actions`
- 复盘聚合：
  - `GET /api/alert/alerts/{alert_id}/review`

---

## 15. AI 助手与证据链（AI Assistant）

### 15.1 分析任务与运行

- 创建任务：`POST /api/ai/jobs`
- 查询任务：`GET /api/ai/jobs`
- 触发运行：`POST /api/ai/jobs/{job_id}/runs`
- 查询运行：`GET /api/ai/jobs/{job_id}/runs`
- 运行重试：`POST /api/ai/runs/{run_id}/retry`

### 15.2 输出与人审

- 输出列表：`GET /api/ai/outputs`
- 输出详情：`GET /api/ai/outputs/{output_id}`
- 审核动作：`POST /api/ai/outputs/{output_id}/review`
- 审核视图：`GET /api/ai/outputs/{output_id}/review`

说明：
- AI 输出字段 `control_allowed=false`，仅用于辅助分析与建议，不直接控制设备。

---

## 16. KPI 与开放平台（KPI + Open Platform）

### 16.1 KPI 数据

- KPI 快照与热力图：见第 9.3 节。

### 16.2 开放平台管理

- 凭据管理：
  - `POST /api/open-platform/credentials`
  - `GET /api/open-platform/credentials`
- Webhook 管理：
  - `POST /api/open-platform/webhooks`
  - `GET /api/open-platform/webhooks`
  - `POST /api/open-platform/webhooks/{endpoint_id}/dispatch-test`
- 外部适配器入站：
  - `POST /api/open-platform/adapters/events/ingest`
  - `GET /api/open-platform/adapters/events`

说明：
- `ingest` 接口使用签名头鉴权：`X-Open-Key-Id`、`X-Open-Api-Key`、`X-Open-Signature`。

---

## 17. 常见问题（FAQ）

### 17.1 页面返回 401

原因：未登录、会话过期，或 token 无效。  
处理：优先重新访问 `/ui/login` 登录；如使用直达链接，再确认 `?token=<token>` 是否有效。

### 17.2 页面返回 403

原因：当前账号缺少模块权限。  
处理：管理员在身份模块为角色绑定对应权限，再重新登录。

### 17.3 看不到数据

原因：租户隔离导致只能看到当前租户数据。  
处理：确认登录账号与业务数据处于同一 `tenant_id`。

### 17.4 导出文件找不到

原因：导出成功但文件被清理或路径变化。  
处理：检查 `logs/exports/`，必要时重新触发导出接口。

---

## 18. 验收建议命令

```powershell
docker --context default compose -f infra/docker-compose.yml run --rm --build app-tools ruff check app tests infra/scripts
docker --context default compose -f infra/docker-compose.yml run --rm --build app-tools mypy app
docker --context default compose -f infra/docker-compose.yml run --rm --build app-tools pytest
docker --context default compose -f infra/docker-compose.yml run --rm --build -e APP_BASE_URL=http://app:8000 app-tools python infra/scripts/verify_smoke.py
```

---

## 19. 附录：关键页面与接口索引

### 页面

- `/ui/console`
- `/ui/inspection`
- `/ui/inspection/tasks/{task_id}`
- `/ui/defects`
- `/ui/emergency`
- `/ui/command-center`
- `/ui/alerts`
- `/ui/reports`
- `/ui/platform`

### API 分组

- 身份与权限：`/api/identity/*`
- 巡查：`/api/inspection/*`
- 问题闭环：`/api/defects/*`
- 应急：`/api/incidents/*`
- 指挥大屏：`/api/dashboard/*` + `/ws/dashboard`
- 合规：`/api/compliance/*` + `/api/approvals/*`
- 告警：`/api/alert/*`
- 成果目录：`/api/outcomes/*`
- AI 助手：`/api/ai/*`
- KPI：`/api/kpi/*`
- 开放平台：`/api/open-platform/*`
- 报表：`/api/reporting/*`
- 租户导出与清理：`/api/tenants/*`

