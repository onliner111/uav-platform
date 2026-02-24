# 城市低空综合治理与应急指挥平台
# 接口清单附录（V2.0）

- 文档版本：V2.0
- 更新日期：2026-02-24
- 说明：本附录按模块整理当前系统已实现接口，路径与 `app/main.py` 路由注册一致。

---

## 1. 鉴权与通用说明

1. 受保护接口需携带请求头：`Authorization: Bearer <access_token>`
2. UI 页面使用查询参数：`?token=<access_token>`
3. 健康检查接口无需鉴权：`/healthz`、`/readyz`

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
| POST | `/api/identity/users/{user_id}/roles:batch-bind` | 批量绑定用户角色（返回逐项结果） |
| POST | `/api/identity/users/{user_id}/roles/{role_id}` | 用户绑定角色 |
| DELETE | `/api/identity/users/{user_id}/roles/{role_id}` | 用户解绑角色 |
| POST | `/api/identity/roles/{role_id}/permissions/{permission_id}` | 角色绑定权限 |
| DELETE | `/api/identity/roles/{role_id}/permissions/{permission_id}` | 角色解绑权限 |

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
| POST | `/api/reporting/export` | 导出报表文件 |

---

## 15. UI 页面接口（`/ui/*`）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/ui` | UI 首页（重定向） |
| GET | `/ui/inspection` | 巡查任务列表页 |
| GET | `/ui/inspection/tasks/{task_id}` | 巡查任务地图详情页 |
| GET | `/ui/defects` | 问题闭环页 |
| GET | `/ui/emergency` | 应急处置页 |
| GET | `/ui/command-center` | 指挥中心大屏页 |

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

