# Phase 08A - 组织层级与 RBAC 基座

## 0. Basis
- Based on: `phases/phase-08-one-net-unified-flight-planning.md`
- Goal mapping: `项目最终目标.md` -> A. 组织与权限
- Existing baseline:
  - `app/services/identity_service.py`
  - `app/api/routers/identity.py`
  - `app/domain/models.py`
  - `tests/test_identity.py`

## 1. Objective
完成“一网统飞”组织与权限的基础层，形成可扩展的多组织治理模型。

## 2. Scope
- 组织层级模型（租户 -> 组织 -> 部门）与基础 API
- 角色模板与自定义角色模型
- 用户-组织绑定和角色授予基础流程
- RBAC 规则基座（不含跨域数据权限细则）

## 3. Out of Scope
- 设备资源池与运维资产（Phase 09）
- 地图态势与轨迹播放（Phase 10）
- AI 分析与推荐（Phase 14）

## 4. Deliverables
- 数据模型与迁移方案（组织相关表）
- `app/services/identity_service.py` 扩展设计与实现
- 身份/权限 API 变更与 OpenAPI 更新
- 覆盖组织层级与角色授予的测试
- 面向运维的简要使用文档（docs）

## 5. Acceptance
- 支持租户内多组织层级管理
- 角色模板与自定义角色可共存
- 跨组织越权访问被正确拒绝
- 关键授权操作可被审计追踪

## 6. Exit Criteria
- `ruff`, `mypy`, `pytest`, `e2e` 全绿
- Phase 08B 所需的 RBAC 基础能力齐备

---

## 7. Implementation Work Packages (Execution Order)

### 08A-WP1: 组织模型与成员关系（数据层）
Objective:
- 建立租户内组织树与用户组织归属关系。

Schema changes (planned):
- `org_units`（租户内组织节点）
  - `id`, `tenant_id`, `name`, `code`, `parent_id`, `level`, `path`, `is_active`, `created_at`, `updated_at`
- `user_org_memberships`（用户与组织绑定）
  - `tenant_id`, `user_id`, `org_unit_id`, `is_primary`, `created_at`

Constraints (planned):
- `org_units`:
  - `UNIQUE (tenant_id, id)`
  - `UNIQUE (tenant_id, code)`
  - 自关联复合 FK：`(tenant_id, parent_id) -> org_units(tenant_id, id)`（nullable）
- `user_org_memberships`:
  - 复合 FK：`(tenant_id, user_id) -> users(tenant_id, id)`
  - 复合 FK：`(tenant_id, org_unit_id) -> org_units(tenant_id, id)`
  - 复合 PK：`(tenant_id, user_id, org_unit_id)`

Files:
- `app/domain/models.py`
- `infra/migrations/versions/*phase08a_org_rbac_*.py`

### 08A-WP2: RBAC 模板能力（服务层）
Objective:
- 在现有 role 模型上提供模板化创建能力，保留自定义角色。

Service additions (planned):
- 角色模板目录（service 级配置，不强制新增模板表）
- `list_role_templates(tenant_id)`
- `create_role_from_template(tenant_id, template_key, override_name?)`

Behavior:
- 模板角色仅作为创建入口，不改变已有 `roles`/`role_permissions` 主模型。
- 仍遵守租户隔离与跨租户 `404` 语义。

Files:
- `app/services/identity_service.py`
- `app/domain/models.py`（请求/响应 DTO）

### 08A-WP3: 组织与授权 API（路由层）
Objective:
- 提供组织管理与用户组织绑定 API。

API set (planned):
- `POST /api/identity/org-units`
- `GET /api/identity/org-units`
- `GET /api/identity/org-units/{org_unit_id}`
- `PATCH /api/identity/org-units/{org_unit_id}`
- `DELETE /api/identity/org-units/{org_unit_id}`
- `POST /api/identity/users/{user_id}/org-units/{org_unit_id}`
- `DELETE /api/identity/users/{user_id}/org-units/{org_unit_id}`
- `GET /api/identity/users/{user_id}/org-units`
- `GET /api/identity/role-templates`
- `POST /api/identity/roles:from-template`

Permission gates:
- 读操作：`PERM_IDENTITY_READ`
- 写操作：`PERM_IDENTITY_WRITE`

Files:
- `app/api/routers/identity.py`
- `app/domain/permissions.py`（若新增细粒度权限）

### 08A-WP4: 回归测试与文档
Objective:
- 保证组织/RBAC 基座上线后不破坏当前身份能力。

Tests (planned):
- `tests/test_identity.py` 扩展：
  - 组织 CRUD 租户隔离
  - 用户组织绑定跨租户 `404`
  - 模板角色创建成功与权限绑定正确
  - 组织删除保护（有子节点或成员时拒绝）
- 可选新增：`tests/test_identity_org.py`

Docs:
- `docs/Admin_Manual_V2.0.md`（组织与模板角色操作）
- `docs/API_Appendix_V2.0.md`（新增 API）

---

## 8. Migration Strategy

Adopt 3-step strategy:
1. Expand:
   - 新表、索引、nullable 字段先落地
2. Backfill + Validate:
   - 补齐初始根组织与 admin 组织归属（如需要）
   - 校验 parent/path/tenant 一致性
3. Enforce:
   - 打开严格约束（唯一、复合 FK、删除限制）

Naming convention:
- `*_phase08a_org_rbac_expand.py`
- `*_phase08a_org_rbac_backfill_validate.py`
- `*_phase08a_org_rbac_enforce.py`

---

## 9. Acceptance Matrix (Detailed)

- 组织模型:
  - 同租户可建立树结构；跨租户 parent 绑定失败
- 用户归属:
  - 用户可绑定多个组织；主组织规则可验证
- 角色模板:
  - 可列出模板并基于模板创建租户角色
- 安全语义:
  - 跨租户资源访问返回 `404`
  - 未授权访问返回 `403`
- 审计:
  - 组织创建、绑定、解绑、删除均有审计记录

---

## 10. Verification Commands

Use docker compose based gates:
- `docker compose -f infra/docker-compose.yml run --rm --build app ruff check app tests infra/scripts`
- `docker compose -f infra/docker-compose.yml run --rm --build app mypy app`
- `docker compose -f infra/docker-compose.yml run --rm --build app pytest -q`
- `docker compose -f infra/docker-compose.yml up --build -d`
- `docker compose -f infra/docker-compose.yml run --rm --build app alembic upgrade head`
- `docker compose -f infra/docker-compose.yml run --rm --build -e APP_BASE_URL=http://app:8000 app-tools python infra/scripts/demo_e2e.py`
- `docker compose -f infra/docker-compose.yml run --rm --build -e APP_BASE_URL=http://app:8000 app-tools python infra/scripts/verify_smoke.py`

---

## 11. Phase 08A Done Definition

- 08A-WP1 ~ 08A-WP4 全部完成
- 质量门禁全绿
- `phases/state.md` 更新到下一阶段（08B）或按执行策略进入 08A 后续批次
- `docs/PROJECT_STATUS.md` 与 `logs/PROGRESS.md` 同步

---

## 12. Execution Progress

- [x] 08A-WP1:
  - Added `OrgUnit` and `UserOrgMembership` models in `app/domain/models.py`
  - Added migrations:
    - `202602240029_phase08a_org_rbac_expand.py`
    - `202602240030_phase08a_org_rbac_backfill_validate.py`
    - `202602240031_phase08a_org_rbac_enforce.py`
  - Added DB boundary tests: `tests/test_identity_org.py`
  - Verification:
    - `docker compose -f infra/docker-compose.yml run --rm --build app pytest tests/test_identity_org.py -q` -> pass
- [x] 08A-WP2:
  - Added role template DTOs in `app/domain/models.py`:
    - `RoleTemplateRead`
    - `RoleFromTemplateCreateRequest`
  - Added role template catalog and service methods in `app/services/identity_service.py`:
    - `list_role_templates()`
    - `create_role_from_template(tenant_id, template_key, name=None)`
  - Added template APIs in `app/api/routers/identity.py`:
    - `GET /api/identity/role-templates`
    - `POST /api/identity/roles:from-template`
  - Added regression tests in `tests/test_identity.py`:
    - `test_identity_role_templates_list_and_create`
    - `test_identity_role_template_not_found`
  - Verification:
    - `docker compose -f infra/docker-compose.yml run --rm --build app pytest tests/test_identity.py tests/test_identity_org.py -q` -> pass
    - `docker compose -f infra/docker-compose.yml run --rm --build app ruff check app/api/routers/identity.py app/domain/models.py app/services/identity_service.py tests/test_identity.py tests/test_identity_org.py` -> pass
    - `docker compose -f infra/docker-compose.yml run --rm --build app mypy app/services/identity_service.py app/domain/models.py app/api/routers/identity.py` -> pass
- [x] 08A-WP3:
  - Added org APIs in `app/api/routers/identity.py`:
    - `POST /api/identity/org-units`
    - `GET /api/identity/org-units`
    - `GET /api/identity/org-units/{org_unit_id}`
    - `PATCH /api/identity/org-units/{org_unit_id}`
    - `DELETE /api/identity/org-units/{org_unit_id}`
    - `POST /api/identity/users/{user_id}/org-units/{org_unit_id}`
    - `DELETE /api/identity/users/{user_id}/org-units/{org_unit_id}`
    - `GET /api/identity/users/{user_id}/org-units`
  - Added org service logic in `app/services/identity_service.py`:
    - org create/list/get/update/delete (with tenant scope + cycle/child/member guards)
    - user-org bind/unbind/list (with primary switch behavior)
  - Added org DTOs in `app/domain/models.py`:
    - `OrgUnitCreate/Update/Read`
    - `UserOrgMembershipBindRequest`
    - `UserOrgMembershipLinkRead`
- [x] 08A-WP4:
  - Added tests in `tests/test_identity.py`:
    - `test_identity_org_units_crud_and_membership_guards`
    - `test_identity_org_units_cross_tenant_returns_404`
  - Updated docs:
    - `docs/API_Appendix_V2.0.md`
    - `docs/Admin_Manual_V2.0.md`
  - Full phase gate verification:
    - `docker compose -f infra/docker-compose.yml up --build -d` -> pass
    - `docker compose -f infra/docker-compose.yml run --rm --build app alembic upgrade head` -> pass (`202602240031`)
    - `docker compose -f infra/docker-compose.yml run --rm --build app ruff check app tests infra/scripts` -> pass
    - `docker compose -f infra/docker-compose.yml run --rm --build app mypy app` -> pass
    - `docker compose -f infra/docker-compose.yml run --rm --build app pytest -q` -> pass
    - `docker compose -f infra/docker-compose.yml run --rm --build -e APP_BASE_URL=http://app:8000 app-tools python infra/scripts/demo_e2e.py` -> pass
    - `docker compose -f infra/docker-compose.yml run --rm --build -e APP_BASE_URL=http://app:8000 app-tools python infra/scripts/verify_smoke.py` -> pass
