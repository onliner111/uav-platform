# 城市低空综合治理与应急指挥平台
# 接口清单附录（V3.0）

- 文档版本：V3.0
- 更新日期：2026-03-02
- 说明：本附录按模块整理当前系统已实现接口，路径与 `app/main.py` 路由注册一致（覆盖至 `phase-39`；`phase-40` 至 `phase-43` 仅为规划，尚未进入执行）。

## 0. 建议谁看这份文档

适合阅读：

- 交付工程师
- 联调工程师
- 技术支持
- 平台管理员（需要排查或核对接口时）

不建议作为首选文档的读者：

- 普通业务用户
- 首次培训的非技术管理员

阅读建议：

1. 先看 [文档导航_V3.0.md](./文档导航_V3.0.md) 确认自己是否需要直接阅读本附录
2. 如需了解系统边界，再配合 [Architecture_Overview_V3.0.md](./Architecture_Overview_V3.0.md) 一起阅读

---

## 1. 鉴权与通用说明

1. 受保护接口需携带请求头：`Authorization: Bearer <access_token>`
2. 推荐 UI 通过会话登录使用：`/ui/login`
3. 兼容 UI 查询参数：`?token=<access_token>`
4. 健康检查接口无需鉴权：`/healthz`、`/readyz`
5. 开放平台适配器入口使用签名头鉴权：`X-Open-Key-Id`、`X-Open-Api-Key`、`X-Open-Signature`

---

## 2. 系统健康接口

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/healthz` | 存活检查 |
| GET | `/readyz` | 就绪检查（DB/Redis） |

---

## 3. 身份与权限（`/api/identity`）

### 3.1 租户与登录

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/identity/tenants` | 创建租户 |
| GET | `/api/identity/tenants` | 查询当前租户 |
| GET | `/api/identity/tenants/{tenant_id}` | 租户详情 |
| PATCH | `/api/identity/tenants/{tenant_id}` | 更新租户 |
| DELETE | `/api/identity/tenants/{tenant_id}` | 删除租户 |
| POST | `/api/identity/bootstrap-admin` | 初始化管理员 |
| POST | `/api/identity/dev-login` | 登录获取 JWT |

### 3.2 用户、角色、权限

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/identity/users` | 创建用户 |
| GET | `/api/identity/users` | 用户列表 |
| GET | `/api/identity/users/{user_id}` | 用户详情 |
| PATCH | `/api/identity/users/{user_id}` | 更新用户 |
| DELETE | `/api/identity/users/{user_id}` | 删除用户 |
| POST | `/api/identity/roles` | 创建角色 |
| GET | `/api/identity/roles` | 角色列表 |
| GET | `/api/identity/roles/{role_id}` | 角色详情 |
| PATCH | `/api/identity/roles/{role_id}` | 更新角色 |
| DELETE | `/api/identity/roles/{role_id}` | 删除角色 |
| GET | `/api/identity/role-templates` | 角色模板列表 |
| POST | `/api/identity/roles:from-template` | 基于模板创建角色 |
| POST | `/api/identity/permissions` | 创建权限 |
| GET | `/api/identity/permissions` | 权限列表 |
| GET | `/api/identity/permissions/{permission_id}` | 权限详情 |
| PATCH | `/api/identity/permissions/{permission_id}` | 更新权限 |
| DELETE | `/api/identity/permissions/{permission_id}` | 删除权限 |
| POST | `/api/identity/org-units` | 创建组织节点 |
| GET | `/api/identity/org-units` | 组织节点列表 |
| GET | `/api/identity/org-units/{org_unit_id}` | 组织节点详情 |
| PATCH | `/api/identity/org-units/{org_unit_id}` | 更新组织节点 |
| DELETE | `/api/identity/org-units/{org_unit_id}` | 删除组织节点 |
| POST | `/api/identity/users/{user_id}/org-units/{org_unit_id}` | 用户绑定组织 |
| DELETE | `/api/identity/users/{user_id}/org-units/{org_unit_id}` | 用户解绑组织 |
| GET | `/api/identity/users/{user_id}/org-units` | 查询用户组织绑定 |
| GET | `/api/identity/users/{user_id}/data-policy` | 查询用户数据边界策略 |
| PUT | `/api/identity/users/{user_id}/data-policy` | 设置用户数据边界策略 |
| GET | `/api/identity/users/{user_id}/data-policy:effective` | 查询用户有效数据边界策略（显式/继承/冲突解析结果） |
| GET | `/api/identity/roles/{role_id}/data-policy` | 查询角色继承数据边界策略 |
| PUT | `/api/identity/roles/{role_id}/data-policy` | 设置角色继承数据边界策略 |
| POST | `/api/identity/users/{user_id}/roles:batch-bind` | 批量绑定用户角色（返回逐项结果） |
| POST | `/api/identity/users/{user_id}/roles/{role_id}` | 用户绑定角色 |
| DELETE | `/api/identity/users/{user_id}/roles/{role_id}` | 用户解绑角色 |
| POST | `/api/identity/roles/{role_id}/permissions/{permission_id}` | 角色绑定权限 |
| DELETE | `/api/identity/roles/{role_id}/permissions/{permission_id}` | 角色解绑权限 |
| GET | `/api/identity/platform/tenants` | 平台超管查看全租户列表（需显式 `platform.super_admin`） |
| GET | `/api/identity/platform/tenants/{tenant_id}/users` | 平台超管查看指定租户用户列表 |

组织与岗位字段补充：
- `OrgUnit` 支持 `unit_type`：`ORGANIZATION` / `DEPARTMENT`
- 用户组织绑定请求支持：`is_primary`、`job_title`、`job_code`、`is_manager`
- 用户数据边界策略支持 `resource_ids`（资源级过滤，适用于资产与设备）
- 用户数据边界策略支持显式拒绝维度：`denied_org_unit_ids`、`denied_project_codes`、`denied_area_codes`、`denied_task_ids`、`denied_resource_ids`
- 冲突解析顺序固定为：`explicit_deny > explicit_allow > inherited_allow > default_deny`

---

## 4. 设备注册（`/api/registry`）

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/registry/drones` | 注册无人机 |
| GET | `/api/registry/drones` | 无人机列表 |
| GET | `/api/registry/drones/{drone_id}` | 无人机详情 |
| PATCH | `/api/registry/drones/{drone_id}` | 更新无人机 |
| DELETE | `/api/registry/drones/{drone_id}` | 删除无人机 |

---

## 5. 任务管理（`/api/mission`）

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/mission/missions` | 创建任务 |
| GET | `/api/mission/missions` | 任务列表 |
| GET | `/api/mission/missions/{mission_id}` | 任务详情 |
| PATCH | `/api/mission/missions/{mission_id}` | 更新任务 |
| DELETE | `/api/mission/missions/{mission_id}` | 删除任务 |
| POST | `/api/mission/missions/{mission_id}/approve` | 审批任务 |
| GET | `/api/mission/missions/{mission_id}/approvals` | 审批记录 |
| POST | `/api/mission/missions/{mission_id}/transition` | 状态迁移 |

---

## 6. 遥测（`/api/telemetry` + WS）

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/telemetry/ingest` | 遥测写入 |
| GET | `/api/telemetry/drones/{drone_id}/latest` | 查询最新遥测 |
| WS | `/ws/drones` | 实时遥测推送 |

---

## 7. 指令（`/api/command`）

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/command/commands` | 下发指令 |
| GET | `/api/command/commands` | 指令列表 |
| GET | `/api/command/commands/{command_id}` | 指令详情 |

---

## 8. 告警（`/api/alert`）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/alert/alerts` | 告警列表 |
| GET | `/api/alert/alerts/{alert_id}` | 告警详情 |
| POST | `/api/alert/alerts/{alert_id}/ack` | 告警确认 |
| POST | `/api/alert/alerts/{alert_id}/close` | 告警关闭 |
| POST | `/api/alert/routing-rules` | 创建告警路由规则 |
| GET | `/api/alert/routing-rules` | 路由规则列表（支持优先级/类型/启用过滤） |
| GET | `/api/alert/alerts/{alert_id}/routes` | 告警路由日志 |
| POST | `/api/alert/alerts/{alert_id}/actions` | 新增处置动作 |
| GET | `/api/alert/alerts/{alert_id}/actions` | 处置动作列表 |
| GET | `/api/alert/alerts/{alert_id}/review` | 告警复盘聚合（告警+路由+动作） |
| POST | `/api/alert/oncall/shifts` | 创建值班班次 |
| GET | `/api/alert/oncall/shifts` | 值班班次列表 |
| POST | `/api/alert/escalation-policies` | 创建升级策略 |
| GET | `/api/alert/escalation-policies` | 升级策略列表 |
| POST | `/api/alert/alerts:escalation-run` | 触发升级运行 |
| POST | `/api/alert/routes/{route_log_id}:receipt` | 写入通知回执 |

---

## 9. 巡查（`/api/inspection`）

### 9.1 模板与检查项

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/inspection/templates` | 模板列表 |
| POST | `/api/inspection/templates` | 创建模板 |
| GET | `/api/inspection/templates/{template_id}` | 模板详情 |
| POST | `/api/inspection/templates/{template_id}/items` | 新增检查项 |
| GET | `/api/inspection/templates/{template_id}/items` | 检查项列表 |

### 9.2 任务与观测

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/inspection/tasks` | 创建巡查任务 |
| GET | `/api/inspection/tasks` | 任务列表 |
| GET | `/api/inspection/tasks/{task_id}` | 任务详情 |
| POST | `/api/inspection/tasks/{task_id}/observations` | 写入观测点 |
| GET | `/api/inspection/tasks/{task_id}/observations` | 查询观测点 |

### 9.3 导出

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/inspection/tasks/{task_id}/export` | 导出任务报告（支持 `format=html`） |
| GET | `/api/inspection/exports/{export_id}` | 下载导出文件 |

---

## 10. 问题闭环（`/api/defects`）

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/defects/from-observation/{observation_id}` | 由观测点生成问题单 |
| GET | `/api/defects` | 问题单列表 |
| GET | `/api/defects/stats` | 闭环统计 |
| GET | `/api/defects/{defect_id}` | 问题详情（含操作历史） |
| POST | `/api/defects/{defect_id}/assign` | 指派处理人 |
| POST | `/api/defects/{defect_id}/status` | 状态流转 |

---

## 11. 应急（`/api/incidents`）

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/incidents` | 创建应急事件 |
| GET | `/api/incidents` | 应急事件列表 |
| POST | `/api/incidents/{incident_id}/create-task` | 一键创建应急任务 |

---

## 12. 指挥中心（`/api/dashboard` + WS）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/dashboard/stats` | 大屏统计数据 |
| GET | `/api/dashboard/observations` | 观测点数据 |
| WS | `/ws/dashboard` | 实时大屏推送 |

---

## 13. 合规审批（`/api/approvals`）

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/approvals` | 新增审批记录 |
| GET | `/api/approvals` | 审批记录列表 |
| GET | `/api/approvals/audit-export` | 审计日志导出 |

---

## 14. 报表（`/api/reporting`）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/reporting/overview` | 总览统计 |
| GET | `/api/reporting/closure-rate` | 闭环率统计 |
| GET | `/api/reporting/device-utilization` | 设备利用率统计 |
| POST | `/api/reporting/export` | 导出报表文件（支持 `task_id/from_ts/to_ts/topic`） |
| POST | `/api/reporting/outcome-report-templates` | 创建成果报告模板 |
| GET | `/api/reporting/outcome-report-templates` | 成果报告模板列表 |
| POST | `/api/reporting/outcome-report-exports` | 创建成果报告导出任务 |
| GET | `/api/reporting/outcome-report-exports` | 成果报告导出任务列表 |

---

## 15. UI 页面接口（`/ui/*`）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/ui` | UI 首页（重定向） |
| GET | `/ui/login` | UI 登录页 |
| POST | `/ui/login` | UI 会话登录 |
| POST | `/ui/logout` | UI 会话登出 |
| GET | `/ui/console` | 角色化工作台首页 |
| GET | `/ui/workbench/{role_key}` | 角色工作台详情页 |
| GET | `/ui/inspection` | 巡查任务列表页 |
| GET | `/ui/inspection/tasks/{task_id}` | 巡查任务地图详情页 |
| GET | `/ui/defects` | 问题闭环页 |
| GET | `/ui/emergency` | 应急处置页 |
| GET | `/ui/command-center` | 指挥中心大屏页 |
| GET | `/ui/task-center` | 任务中心页 |
| GET | `/ui/assets` | 资产台账页 |
| GET | `/ui/compliance` | 合规治理页 |
| GET | `/ui/alerts` | 通知协同中心页 |
| GET | `/ui/reports` | 业务闭环与汇报页 |
| GET | `/ui/platform` | 上线保障与版本运营台 |
| GET | `/ui/observability` | 可观测性管理员页 |
| GET | `/ui/reliability` | 可靠性管理员页 |
| GET | `/ui/ai-governance` | AI 治理管理员页 |
| GET | `/ui/commercial-ops` | 商业运营管理员页 |
| GET | `/ui/open-platform` | 开放平台管理员页 |

---

## 16. 租户导出与清理（`/api/tenants`）

### 16.1 Tenant Export

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/tenants/{tenant_id}/export` | 触发租户导出（支持 `include_zip=true`） |
| GET | `/api/tenants/{tenant_id}/export/{export_id}` | 查询导出状态与 manifest 摘要 |
| GET | `/api/tenants/{tenant_id}/export/{export_id}/download` | 下载导出 zip 包 |

### 16.2 Tenant Purge

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/tenants/{tenant_id}/purge:dry_run` | 生成清理计划与计数（不删除） |
| POST | `/api/tenants/{tenant_id}/purge` | 执行清理（需 `dry_run_id` + 二次确认） |
| GET | `/api/tenants/{tenant_id}/purge/{purge_id}` | 查询清理结果报告 |

---

## 17. 资源台账与资源池（`/api/assets`）

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/assets` | 创建设备/资源台账 |
| GET | `/api/assets` | 资源列表（类型/生命周期/可用性/健康过滤） |
| GET | `/api/assets/{asset_id}` | 资源详情 |
| POST | `/api/assets/{asset_id}/bind` | 绑定任务/主体 |
| POST | `/api/assets/{asset_id}/availability` | 更新可用状态 |
| POST | `/api/assets/{asset_id}/health` | 更新健康状态 |
| POST | `/api/assets/{asset_id}/retire` | 资源退役 |
| GET | `/api/assets/pool` | 资源池查询 |
| GET | `/api/assets/pool/summary` | 区域资源池汇总 |

---

## 18. 空域合规与飞前检查（`/api/compliance`）

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/compliance/zones` | 新增空域规则区 |
| GET | `/api/compliance/zones` | 空域规则区列表 |
| GET | `/api/compliance/zones/{zone_id}` | 空域规则区详情 |
| POST | `/api/compliance/preflight/templates` | 新增飞前检查模板 |
| GET | `/api/compliance/preflight/templates` | 飞前检查模板列表 |
| POST | `/api/compliance/missions/{mission_id}/preflight/init` | 初始化任务飞前检查 |
| GET | `/api/compliance/missions/{mission_id}/preflight` | 查询任务飞前检查 |
| POST | `/api/compliance/missions/{mission_id}/preflight/check-item` | 勾选飞前检查项 |

---

## 19. 一张图态势（`/api/map`）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/map/overview` | 一张图聚合视图 |
| GET | `/api/map/layers/resources` | 资源图层 |
| GET | `/api/map/layers/tasks` | 任务图层 |
| GET | `/api/map/layers/airspace` | 空域图层 |
| GET | `/api/map/layers/alerts` | 告警图层 |
| GET | `/api/map/layers/events` | 事件图层 |
| GET | `/api/map/layers/outcomes` | 成果图层 |
| GET | `/api/map/tracks/replay` | 航迹回放 |

---

## 20. 统一任务中心（`/api/task-center`）

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/task-center/types` | 创建任务类型 |
| GET | `/api/task-center/types` | 任务类型列表 |
| POST | `/api/task-center/templates` | 创建任务模板 |
| GET | `/api/task-center/templates` | 模板列表 |
| POST | `/api/task-center/templates/{template_id}:clone` | 克隆任务模板 |
| POST | `/api/task-center/tasks` | 创建任务中心任务 |
| POST | `/api/task-center/tasks:batch-create` | 批量创建任务中心任务 |
| GET | `/api/task-center/tasks` | 任务列表 |
| GET | `/api/task-center/tasks/{task_id}` | 任务详情 |
| POST | `/api/task-center/tasks/{task_id}/submit-approval` | 提交审批 |
| POST | `/api/task-center/tasks/{task_id}/approve` | 审批决策 |
| POST | `/api/task-center/tasks/{task_id}/dispatch` | 手工派发 |
| POST | `/api/task-center/tasks/{task_id}/auto-dispatch` | 自动派发（含候选评分） |
| POST | `/api/task-center/tasks/{task_id}/transition` | 任务状态流转 |
| PATCH | `/api/task-center/tasks/{task_id}/risk-checklist` | 更新风险清单 |
| POST | `/api/task-center/tasks/{task_id}/attachments` | 新增附件 |
| POST | `/api/task-center/tasks/{task_id}/comments` | 新增评论 |
| GET | `/api/task-center/tasks/{task_id}/comments` | 评论列表 |
| GET | `/api/task-center/tasks/{task_id}/history` | 历史流水 |

---

## 21. 成果目录（`/api/outcomes`）

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/outcomes/raw` | 新增原始数据目录记录 |
| GET | `/api/outcomes/raw` | 原始数据目录列表 |
| POST | `/api/outcomes/raw/uploads:init` | 初始化原始数据上传会话 |
| POST | `/api/outcomes/raw/uploads/{upload_id}/complete` | 完成原始数据上传会话 |
| GET | `/api/outcomes/raw/{raw_id}/download` | 下载原始数据对象 |
| POST | `/api/outcomes/records` | 新增成果记录 |
| POST | `/api/outcomes/records/from-observation/{observation_id}` | 由观测点生成成果记录 |
| GET | `/api/outcomes/records` | 成果记录列表 |
| PATCH | `/api/outcomes/records/{outcome_id}/status` | 更新成果状态 |
| GET | `/api/outcomes/records/{outcome_id}/versions` | 查询成果版本链 |
| POST | `/api/outcomes/records/{outcome_id}/versions` | 新增成果版本 |

---

## 22. AI 助手与证据链（`/api/ai`）

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/ai/jobs` | 创建 AI 分析任务 |
| GET | `/api/ai/jobs` | AI 任务列表 |
| POST | `/api/ai/jobs/{job_id}/runs` | 触发分析运行 |
| GET | `/api/ai/jobs/{job_id}/runs` | 运行列表 |
| POST | `/api/ai/runs/{run_id}/retry` | 运行重试 |
| GET | `/api/ai/outputs` | 输出列表（支持按任务/运行/审核状态筛选） |
| GET | `/api/ai/outputs/{output_id}` | 输出详情 |
| POST | `/api/ai/outputs/{output_id}/review` | 人审动作（通过/驳回/覆写） |
| GET | `/api/ai/outputs/{output_id}/review` | 输出复核视图（输出+动作+证据） |
| GET | `/api/ai/models` | 模型目录列表 |
| POST | `/api/ai/models` | 创建模型目录 |
| GET | `/api/ai/model-versions` | 模型版本列表 |
| POST | `/api/ai/model-versions` | 创建模型版本 |

---

## 23. KPI 与治理报表（`/api/kpi`）

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/kpi/snapshots/recompute` | 重算 KPI 快照 |
| GET | `/api/kpi/snapshots` | KPI 快照列表 |
| GET | `/api/kpi/snapshots/latest` | 最新 KPI 快照 |
| GET | `/api/kpi/heatmap` | KPI 热力图网格数据 |
| POST | `/api/kpi/governance/export` | 导出治理月报/季报 |

---

## 24. 开放平台（`/api/open-platform`）

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/open-platform/credentials` | 创建开放平台凭据（key/api_key/secret） |
| GET | `/api/open-platform/credentials` | 凭据列表 |
| POST | `/api/open-platform/webhooks` | 创建 Webhook 端点 |
| GET | `/api/open-platform/webhooks` | Webhook 列表 |
| POST | `/api/open-platform/webhooks/{endpoint_id}/dispatch-test` | Webhook 发送测试 |
| POST | `/api/open-platform/adapters/events/ingest` | 外部适配器事件入口（签名鉴权） |
| GET | `/api/open-platform/adapters/events` | 外部事件入站记录列表 |

---

## 25. 真实接入与视频（`/api/integration`）

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/integration/device-sessions/start` | 启动设备接入会话 |
| POST | `/api/integration/device-sessions/{session_id}:stop` | 停止设备接入会话 |
| GET | `/api/integration/device-sessions` | 设备接入会话列表 |
| GET | `/api/integration/device-sessions/{session_id}` | 设备接入会话详情 |
| POST | `/api/integration/video-streams` | 创建视频流配置 |
| GET | `/api/integration/video-streams` | 视频流列表 |
| GET | `/api/integration/video-streams/{stream_id}` | 视频流详情 |
| PATCH | `/api/integration/video-streams/{stream_id}` | 更新视频流配置 |
| DELETE | `/api/integration/video-streams/{stream_id}` | 删除视频流配置 |

---

## 26. 可观测性与可靠性（`/api/observability`）

说明：
- 本模块在 UI 中对应管理员专项页，主要面向管理员与运维角色。
- 具体接口较多，建议以 OpenAPI 文档为准：`/docs`

能力范围包括：

- 信号与 SLO 观测
- 备份与恢复演练
- 安全巡检
- 容量策略与预测
