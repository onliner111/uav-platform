# 城市低空综合治理与应急指挥平台
# 管理员操作手册（V2.0）

- 文档版本：V2.0
- 适用范围：平台管理员、业务管理员、安全审计管理员
- 更新日期：2026-02-24

---

## 1. 管理员职责

管理员主要负责：

1. 租户、用户、角色、权限管理
2. 业务模板与基础配置维护
3. 应急与巡查业务过程监督
4. 审批与审计留痕管理
5. 报表统计与导出管理

---

## 2. 管理入口与准备

### 2.1 管理入口

- OpenAPI：`/docs`
- 核心 UI 页面：
  - `/ui/inspection`
  - `/ui/defects`
  - `/ui/emergency`
  - `/ui/command-center`

### 2.2 前置准备

1. 系统服务可用（`/healthz`、`/readyz` 返回 200）
2. 已创建租户并完成管理员引导
3. 管理员账户具备 `*` 或对应管理权限

---

## 3. 账户与权限管理

说明：系统采用租户隔离 + RBAC，所有业务数据均归属 `tenant_id`。

### 3.1 新建租户

接口：`POST /api/identity/tenants`

示例：

```bash
curl -X POST http://localhost:8000/api/identity/tenants \
  -H "Content-Type: application/json" \
  -d '{"name":"city-a"}'
```

### 3.2 初始化租户管理员

接口：`POST /api/identity/bootstrap-admin`

```bash
curl -X POST http://localhost:8000/api/identity/bootstrap-admin \
  -H "Content-Type: application/json" \
  -d '{"tenant_id":"<tenant_id>","username":"admin","password":"admin-pass"}'
```

### 3.3 登录获取令牌

接口：`POST /api/identity/dev-login`

```bash
curl -X POST http://localhost:8000/api/identity/dev-login \
  -H "Content-Type: application/json" \
  -d '{"tenant_id":"<tenant_id>","username":"admin","password":"admin-pass"}'
```

### 3.4 用户与角色管理

常用接口：

- 用户：`/api/identity/users`
- 角色：`/api/identity/roles`
- 角色模板：`GET /api/identity/role-templates`
- 模板建角：`POST /api/identity/roles:from-template`
- 权限：`/api/identity/permissions`
- 批量绑定角色：`POST /api/identity/users/{user_id}/roles:batch-bind`
- 用户绑定角色：`POST /api/identity/users/{user_id}/roles/{role_id}`
- 角色绑定权限：`POST /api/identity/roles/{role_id}/permissions/{permission_id}`

### 3.5 组织管理与用户组织绑定

常用接口：

- 创建组织节点：`POST /api/identity/org-units`
- 查询组织列表：`GET /api/identity/org-units`
- 查询组织详情：`GET /api/identity/org-units/{org_unit_id}`
- 更新组织节点：`PATCH /api/identity/org-units/{org_unit_id}`
- 删除组织节点：`DELETE /api/identity/org-units/{org_unit_id}`
- 用户绑定组织：`POST /api/identity/users/{user_id}/org-units/{org_unit_id}`
- 用户解绑组织：`DELETE /api/identity/users/{user_id}/org-units/{org_unit_id}`
- 查询用户组织：`GET /api/identity/users/{user_id}/org-units`

管理建议：

1. 先建组织树（根组织 -> 子组织），再进行用户绑定。
2. 有子组织或成员绑定时删除组织会被拒绝（409）。
3. 跨租户访问按 404 语义处理，不暴露目标资源存在性。

### 3.6 数据边界策略（08B）

用途：按 `组织/项目/区域/任务` 维度限制用户可见数据范围。

接口：

- 查询策略：`GET /api/identity/users/{user_id}/data-policy`
- 设置策略：`PUT /api/identity/users/{user_id}/data-policy`

示例请求体（`SCOPED`）：

```json
{
  "scope_mode": "SCOPED",
  "org_unit_ids": ["<org_unit_id>"],
  "project_codes": ["PROJ-A"],
  "area_codes": ["AREA-NORTH"],
  "task_ids": []
}
```

说明：

1. `scope_mode=ALL` 表示不限制（租户内全可见）。
2. `scope_mode=SCOPED` 时，非空维度会参与过滤。
3. 未命中的资源在 API 层返回 404 语义。
4. 08C 起策略变更与跨租户拒绝会写入结构化审计字段（`who/when/where/what/result`）。

### 3.6.1 批量授权（08C）

用途：一次请求为用户绑定多角色，返回逐项处理结果，适合批量授权场景。

接口：

- `POST /api/identity/users/{user_id}/roles:batch-bind`

示例请求体：

```json
{
  "role_ids": ["<role_id_a>", "<role_id_b>", "<role_id_c>"]
}
```

返回要点：

1. `bound_count`：本次新绑定数量。
2. `already_bound_count`：已绑定（幂等）数量。
3. `denied_count`：跨租户拒绝数量（`cross_tenant_denied`）。
4. `missing_count`：角色不存在数量（`not_found`）。

### 3.7 推荐角色划分

1. `platform_admin`：全权限（平台运维/应急总指挥）
2. `inspection_manager`：巡查与问题闭环管理
3. `emergency_operator`：应急事件处置
4. `auditor`：审批和审计查询导出
5. `report_viewer`：报表查看与导出

---

## 4. 巡查业务管理

### 4.1 巡查模板管理

管理员维护模板及检查项，建议每季度复审。

关键接口：

- `GET/POST /api/inspection/templates`
- `POST /api/inspection/templates/{id}/items`
- `GET /api/inspection/templates/{id}/items`

### 4.2 巡查任务监管

- 任务创建：`POST /api/inspection/tasks`
- 任务查询：`GET /api/inspection/tasks`
- 任务详情：`GET /api/inspection/tasks/{id}`
- UI：`/ui/inspection?token=<token>`

### 4.3 巡查结果与导出监管

- 观测点写入：`POST /api/inspection/tasks/{task_id}/observations`
- 观测点查询：`GET /api/inspection/tasks/{task_id}/observations`
- 导出：`POST /api/inspection/tasks/{task_id}/export?format=html`

建议：

1. 每周抽检导出报告质量与字段完整性。
2. 对高严重度问题设置专人跟踪闭环。

---

## 5. 问题闭环管理

### 5.1 问题单生成与指派

- 生成问题单：`POST /api/defects/from-observation/{observation_id}`
- 指派：`POST /api/defects/{id}/assign`

### 5.2 状态流转规范

系统内置流程：

`OPEN -> ASSIGNED -> IN_PROGRESS -> FIXED -> VERIFIED -> CLOSED`

接口：

- `POST /api/defects/{id}/status`

### 5.3 闭环统计

- 统计接口：`GET /api/defects/stats`
- 管理页面：`/ui/defects?token=<token>`

管理员要求：

1. 每日检查闭环率和积压量。
2. 对超期单据执行催办和复核。

---

## 6. 应急管理

### 6.1 应急事件创建

- `POST /api/incidents`

### 6.2 一键任务生成

- `POST /api/incidents/{id}/create-task`

页面：

- `/ui/emergency?token=<token>`

管理员要求：

1. 应急事件需记录等级、位置、责任人。
2. 事件处置后应更新状态并纳入复盘。

---

## 7. 指挥中心管理

页面：`/ui/command-center?token=<token>`

数据接口：

- `GET /api/dashboard/stats`
- `WS /ws/dashboard?token=<token>`

管理员重点关注：

1. 在线设备数量异常波动
2. 告警突增
3. 高严重度观测点分布

---

## 8. 审批与审计管理

### 8.1 审批记录

- 新增审批：`POST /api/approvals`
- 查询审批：`GET /api/approvals`

### 8.2 审计导出

- `GET /api/approvals/audit-export`
- 文件目录：`logs/exports/`

建议：

1. 每周归档审计导出文件
2. 对关键动作进行抽查（任务创建、应急、审批、导出）

---

## 9. 报表管理

接口：

- `GET /api/reporting/overview`
- `GET /api/reporting/closure-rate`
- `GET /api/reporting/device-utilization`
- `POST /api/reporting/export`

管理员建议：

1. 月度汇总：巡查量、问题量、闭环率
2. 季度汇总：设备利用率、应急响应情况

---

## 10. 租户级数据导出与清理管理（07C）

适用场景：
1. 租户数据交付（导出）
2. 租户下线前数据清理（purge）
3. 合规审计取证（manifest/report）

### 10.1 导出流程（建议）

1. 触发导出：`POST /api/tenants/{tenant_id}/export?include_zip=true`
2. 轮询状态：`GET /api/tenants/{tenant_id}/export/{export_id}`
3. 下载归档：`GET /api/tenants/{tenant_id}/export/{export_id}/download`

归档文件：
- `logs/exports/<tenant_id>/<export_id>/manifest.json`
- `logs/exports/<tenant_id>/<export_id>/<export_id>.zip`（启用 `include_zip=true` 时）

### 10.2 清理流程（强保护栏）

1. 执行 dry-run：`POST /api/tenants/{tenant_id}/purge:dry_run`
2. 审核 `plan/counts/safety` 后再执行真删
3. 执行 purge：`POST /api/tenants/{tenant_id}/purge`
4. 查询结果：`GET /api/tenants/{tenant_id}/purge/{purge_id}`

执行 purge 时请求体至少包含：
- `dry_run_id`
- `confirm_token` 或 `confirm_phrase`

固定确认短语：
- `I_UNDERSTAND_THIS_WILL_DELETE_TENANT_DATA`

结果文件：
- `logs/purge/<tenant_id>/<purge_id>/report.json`

### 10.3 管理要求

1. 严禁跳过 dry-run 直接清理。
2. 清理前必须完成导出归档。
3. 所有导出与清理动作纳入审计留痕。
4. 跨租户访问按系统规则返回 404 语义。

---
## 11. 管理员日常巡检清单

每日：

1. 检查 `healthz/readyz`
2. 检查前一日问题闭环率
3. 检查应急事件是否有未处理项

每周：

1. 导出审计日志并归档
2. 复核角色权限最小化原则
3. 抽查巡查导出报告

每月：

1. 导出报表并形成管理简报
2. 清理无效账户和历史临时角色

---

## 12. 常见管理问题

### 12.1 403 无权限

处理：检查用户角色、角色权限绑定，重新登录刷新 token。

### 12.2 看不到数据

处理：确认当前账号所属租户与目标数据租户一致。

### 12.3 导出失败

处理：检查服务写盘权限与 `logs/exports/` 目录状态；租户导出接口可先查询状态接口确认任务结果。

### 12.4 清理执行失败

处理：
1. 确认已先执行 dry-run 并使用正确 `dry_run_id`。
2. 确认 `confirm_token` 或 `confirm_phrase` 有效。
3. 通过 `GET /api/tenants/{tenant_id}/purge/{purge_id}` 查看失败详情。

---

## 13. 接口清单附录

详细接口请参见：`docs/API_Appendix_V2.0.md`。
建议在系统升级后同步复核该附录中的路径与权限要求。
