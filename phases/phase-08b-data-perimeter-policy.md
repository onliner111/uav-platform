# Phase 08B - 数据权限边界策略

## 0. Basis
- Based on: `phases/phase-08-one-net-unified-flight-planning.md`
- Depends on: `phases/phase-08a-org-rbac-foundation.md`

## 1. Objective
建立“按组织/项目/区域/任务”的数据权限边界策略，并在核心业务域落地。

## 2. Scope
- 数据权限策略模型（Org/Project/Area/Task 维度）
- 任务、巡检、缺陷、事件、报表等核心查询路径策略接入
- 统一权限判定入口与策略配置结构
- 跨组织与跨范围访问拒绝语义统一

## 3. Out of Scope
- 空域合规与围栏策略（Phase 12）
- 统计考核体系（Phase 15）

## 4. Deliverables
- 策略模型与配置文档
- 关键 service 查询过滤改造清单
- API 层策略依赖集成
- 数据权限回归测试（正向 + 逆向）

## 5. Acceptance
- 支持按组织/项目/区域/任务组合授权
- 未授权数据在 API 层不可见
- 跨租户访问保持既有 `404` 语义
- 策略变更后可回归验证

## 6. Exit Criteria
- 全量权限用例通过
- 对核心域无行为回归
- 进入 08C 的审计强化输入准备完成

---

## 7. Implementation Packages

### 08B-WP1: 策略模型与迁移
- 新增 `data_access_policies`（按用户配置 `ALL/SCOPED` + org/project/area/task 四维列表）。
- 为核心资源补充范围字段：
  - `missions`: `org_unit_id/project_code/area_code`
  - `inspection_tasks`: `org_unit_id/project_code/area_code`
  - `defects`: `task_id/org_unit_id/project_code/area_code`
  - `incidents`: `org_unit_id/project_code/area_code`
- 迁移链路：
  - `202602240032_phase08b_data_perimeter_expand.py`
  - `202602240033_phase08b_data_perimeter_backfill_validate.py`
  - `202602240034_phase08b_data_perimeter_enforce.py`

### 08B-WP2: 统一判定入口与 API 接入
- 新增统一判定组件：`app/services/data_perimeter_service.py`
- 新增身份接口：
  - `GET /api/identity/users/{user_id}/data-policy`
  - `PUT /api/identity/users/{user_id}/data-policy`
- 接入核心查询路径（按 `claims["sub"]` 进行策略过滤）：
  - mission / inspection / defect / incident / reporting
  - UI 对应页面读取链路同步策略口径

### 08B-WP3: 回归测试与文档
- 新增测试：`tests/test_data_perimeter.py`
- 扩展身份测试：`tests/test_identity.py`（data-policy API）
- 文档更新：
  - `docs/API_Appendix_V2.0.md`
  - `docs/Admin_Manual_V2.0.md`

---

## 8. Execution Progress

- [x] 08B-WP1: 数据模型与迁移链路完成（`032/033/034`）
- [x] 08B-WP2: 统一判定入口与核心域接入完成
- [x] 08B-WP3: 测试与文档更新完成

Verification:
- `docker compose -f infra/docker-compose.yml run --rm --build app alembic upgrade head` -> pass (`202602240034`)
- `docker compose -f infra/docker-compose.yml run --rm --build app ruff check app tests infra/scripts` -> pass
- `docker compose -f infra/docker-compose.yml run --rm --build app mypy app` -> pass
- `docker compose -f infra/docker-compose.yml run --rm --build app pytest -q` -> pass
- `docker compose -f infra/docker-compose.yml run --rm --build -e APP_BASE_URL=http://app:8000 app-tools python infra/scripts/demo_e2e.py` -> pass
- `docker compose -f infra/docker-compose.yml run --rm --build -e APP_BASE_URL=http://app:8000 app-tools python infra/scripts/verify_smoke.py` -> pass
