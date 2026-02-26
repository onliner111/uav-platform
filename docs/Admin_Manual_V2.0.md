# 城市低空综合治理与应急指挥平台
# 管理员操作手册（V2.0）

- 文档版本：V2.0
- 适用范围：平台管理员、业务管理员、安全审计管理员
- 更新日期：2026-02-25

---

## 1. 管理员职责

管理员主要负责：

1. 租户、用户、角色、权限管理
2. 业务模板与基础配置维护
3. 应急与巡查业务过程监督
4. 审批与审计留痕管理
5. 报表统计与导出管理
6. 成果目录与告警处置治理
7. AI 产出人审与责任追踪
8. 开放平台凭据与 Webhook 治理

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
4. 组织节点建议显式设置 `unit_type`（`ORGANIZATION` / `DEPARTMENT`）。
5. 用户绑定组织时可写入岗位信息（`job_title`、`job_code`、`is_manager`）。

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
  "task_ids": [],
  "resource_ids": ["<asset_or_drone_id>"],
  "denied_org_unit_ids": [],
  "denied_project_codes": [],
  "denied_area_codes": [],
  "denied_task_ids": [],
  "denied_resource_ids": []
}
```

说明：

1. `scope_mode=ALL` 表示不限制（租户内全可见）。
2. `scope_mode=SCOPED` 时，非空维度会参与过滤。
3. 未命中的资源在 API 层返回 404 语义。
4. 08C 起策略变更与跨租户拒绝会写入结构化审计字段（`who/when/where/what/result`）。
5. 17-P2 起支持显式拒绝维度（`denied_*`），并按固定顺序解析冲突：`explicit_deny > explicit_allow > inherited_allow > default_deny`。

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

### 3.6.2 平台超管治理（17-WP3）

用途：提供跨租户治理只读入口（租户清单、按租户查看用户）。

接口：

- `GET /api/identity/platform/tenants`
- `GET /api/identity/platform/tenants/{tenant_id}/users`

授权要求：

1. 必须显式拥有 `platform.super_admin` 权限。
2. 仅 `*`（wildcard）权限不足以调用该入口。

### 3.6.3 角色继承策略与冲突解析（17-P2）

用途：通过角色策略提供“继承允许”，并与用户显式允许/显式拒绝组合计算最终可见范围。

接口：

- `GET /api/identity/roles/{role_id}/data-policy`
- `PUT /api/identity/roles/{role_id}/data-policy`
- `GET /api/identity/users/{user_id}/data-policy:effective`

建议流程：

1. 先在角色上配置公共可见域（继承允许）。
2. 再在用户上写入显式允许或显式拒绝，处理例外。
3. 通过 `data-policy:effective` 校验最终结果是否符合预期。

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
3. 使用 `POST /api/kpi/governance/export` 固化月报/季报归档。

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
## 11. 成果与告警闭环治理（13）

### 11.1 成果目录治理

- 原始数据目录：
  - `POST /api/outcomes/raw`
  - `GET /api/outcomes/raw`
- 成果记录：
  - `POST /api/outcomes/records`
  - `GET /api/outcomes/records`
  - `PATCH /api/outcomes/records/{outcome_id}/status`

治理建议：
1. 对高风险成果建立复核责任人。
2. 按任务/专题定期抽查成果状态（`NEW/IN_REVIEW/RESOLVED`）。

### 11.2 告警路由与处置治理

- 路由规则：
  - `POST /api/alert/routing-rules`
  - `GET /api/alert/routing-rules`
- 路由日志：`GET /api/alert/alerts/{alert_id}/routes`
- 处置动作：
  - `POST /api/alert/alerts/{alert_id}/actions`
  - `GET /api/alert/alerts/{alert_id}/actions`
- 复盘视图：`GET /api/alert/alerts/{alert_id}/review`

治理建议：
1. 将 P1/P2 告警与值守班组目标绑定，规则变更纳入审批。
2. 每周复盘 `review` 聚合，检查处置链完整性与时效性。

---

## 12. AI 助手治理（14）

### 12.1 任务与运行治理

- `POST /api/ai/jobs`
- `GET /api/ai/jobs`
- `POST /api/ai/jobs/{job_id}/runs`
- `GET /api/ai/jobs/{job_id}/runs`
- `POST /api/ai/runs/{run_id}/retry`

### 12.2 人审与责任追踪

- 输出：
  - `GET /api/ai/outputs`
  - `GET /api/ai/outputs/{output_id}`
- 人审动作：
  - `POST /api/ai/outputs/{output_id}/review`
  - `GET /api/ai/outputs/{output_id}/review`

治理要求：
1. AI 输出仅作辅助决策，保持 `control_allowed=false` 非控制约束。
2. 关键输出必须完成人审动作并保留审计记录。
3. 覆写（override）需记录原因与责任人。

---

## 13. KPI 与开放平台治理（15）

### 13.1 KPI 与治理报表

- `POST /api/kpi/snapshots/recompute`
- `GET /api/kpi/snapshots`
- `GET /api/kpi/snapshots/latest`
- `GET /api/kpi/heatmap`
- `POST /api/kpi/governance/export`

治理建议：
1. 固定窗口（月/季）生成快照，避免跨周期口径漂移。
2. 报表导出后在 `logs/exports/` 做归档与版本留存。

### 13.2 开放平台安全治理

- 凭据：
  - `POST /api/open-platform/credentials`
  - `GET /api/open-platform/credentials`
- Webhook：
  - `POST /api/open-platform/webhooks`
  - `GET /api/open-platform/webhooks`
  - `POST /api/open-platform/webhooks/{endpoint_id}/dispatch-test`
- 适配器入站：
  - `POST /api/open-platform/adapters/events/ingest`
  - `GET /api/open-platform/adapters/events`

治理要求：
1. 入站事件统一启用签名头：`X-Open-Key-Id`、`X-Open-Api-Key`、`X-Open-Signature`。
2. Webhook 建议使用专用凭据并定期轮换。
3. 生产环境禁用无审计来源的临时 key。

---

## 14. 管理员日常巡检清单

每日：

1. 检查 `healthz/readyz`
2. 检查前一日问题闭环率
3. 检查应急事件是否有未处理项

每周：

1. 导出审计日志并归档
2. 复核角色权限最小化原则
3. 抽查巡查导出报告
4. 抽查 AI 人审动作链与开放平台入站签名有效率

每月：

1. 导出报表并形成管理简报
2. 清理无效账户和历史临时角色
3. 复盘 KPI 热力图趋势并更新治理策略

---

## 15. 常见管理问题

### 15.1 403 无权限

处理：检查用户角色、角色权限绑定，重新登录刷新 token。

### 15.2 看不到数据

处理：确认当前账号所属租户与目标数据租户一致。

### 15.3 导出失败

处理：检查服务写盘权限与 `logs/exports/` 目录状态；租户导出接口可先查询状态接口确认任务结果。

### 15.4 清理执行失败

处理：
1. 确认已先执行 dry-run 并使用正确 `dry_run_id`。
2. 确认 `confirm_token` 或 `confirm_phrase` 有效。
3. 通过 `GET /api/tenants/{tenant_id}/purge/{purge_id}` 查看失败详情。

---

## 16. 接口清单附录

详细接口请参见：`docs/API_Appendix_V2.0.md`。
建议在系统升级后同步复核该附录中的路径与权限要求。
