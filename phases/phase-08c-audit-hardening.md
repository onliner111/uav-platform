# Phase 08C - 审计强化与关键动作留痕

## 0. Basis
- Based on: `phases/phase-08-one-net-unified-flight-planning.md`
- Depends on: `phases/phase-08a-org-rbac-foundation.md`, `phases/phase-08b-data-perimeter-policy.md`

## 1. Objective
确保“关键动作全留痕”，满足一网统飞的治理可追溯要求。

## 2. Scope
- 审计范围清单补齐（登录、授权、任务、指令、导出等）
- 审计事件字段标准化（who/when/where/what/result）
- 导出与下载类动作审计覆盖
- 审计查询与导出接口一致性验证

## 3. Out of Scope
- 告警闭环业务规则增强（Phase 13）
- 外部联动通知网关（Phase 13/15）

## 4. Deliverables
- 审计覆盖矩阵更新
- 审计中间件/服务增强实现
- 审计 API 与文档补充
- 审计回归测试（含导出类动作）

## 5. Acceptance
- 关键动作 100% 进入审计链路
- 审计记录可按租户、操作者、动作类型检索
- 导出/下载操作具备可追溯记录

## 6. Exit Criteria
- 审计覆盖检查通过
- 与权限策略行为一致，无冲突
- 可以进入 08D 集成验收

---

## 7. Execution Progress

- [x] 08C-WP1 审计字段标准化：
  - `app/infra/audit.py` 增加统一 `detail` 结构（`who/when/where/what/result`）
  - 支持路由层注入审计上下文（动作名、目标对象、结果语义）
  - 将 `GET /export`、`GET /download` 纳入审计范围
- [x] 08C-WP2 关键权限动作强化：
  - 策略变更审计：`GET/PUT /api/identity/users/{user_id}/data-policy`
  - 跨域拒绝审计：补充 `cross_tenant_boundary` 原因字段
  - 批量授权能力：新增 `POST /api/identity/users/{user_id}/roles:batch-bind`
- [x] 08C-WP3 回归测试与文档：
  - `tests/test_identity.py` 新增 08C 场景用例（策略变更/跨域拒绝/批量授权审计）
  - `docs/API_Appendix_V2.0.md`、`docs/Admin_Manual_V2.0.md` 同步新增接口与审计说明
- [x] 08C-WP4 全量门禁：
  - `docker compose -f infra/docker-compose.yml run --rm --build app ruff check app tests infra/scripts` -> pass
  - `docker compose -f infra/docker-compose.yml run --rm --build app mypy app` -> pass
  - `docker compose -f infra/docker-compose.yml run --rm --build app pytest -q` -> pass
  - `docker compose -f infra/docker-compose.yml up --build -d` -> pass
  - `docker compose -f infra/docker-compose.yml run --rm --build app alembic upgrade head` -> pass
  - `docker compose -f infra/docker-compose.yml run --rm --build app-tools python -m app.infra.openapi_export` -> pass
  - `docker compose -f infra/docker-compose.yml run --rm --build -e APP_BASE_URL=http://app:8000 app-tools python infra/scripts/demo_e2e.py` -> pass
  - `docker compose -f infra/docker-compose.yml run --rm --build -e APP_BASE_URL=http://app:8000 app-tools python infra/scripts/verify_smoke.py` -> pass
