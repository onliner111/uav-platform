# Phase 08D - 集成验收与 Phase 09 就绪

## 0. Basis
- Based on: `phases/phase-08-one-net-unified-flight-planning.md`
- Depends on: 08A/08B/08C completion

## 1. Objective
完成 Phase 08 的集成验收，形成可复现演示与进入 Phase 09 的基线。

## 2. Scope
- 组织/RBAC/数据权限/审计的端到端联调
- 演示脚本与验收步骤固化
- OpenAPI、测试、文档一致性收敛
- Phase 09 输入清单（资源管理依赖与接口契约）

## 3. Deliverables
- 集成验收报告（logs）
- 演示脚本更新（infra/scripts）
- Phase 09 启动前检查清单
- `phases/state.md` 与 `docs/PROJECT_STATUS.md` 同步

## 4. Acceptance
- 多角色场景端到端可演示
- 关键路径无权限绕过
- 审计证据链完整
- 门禁全通过（lint/typecheck/test/e2e）

## 5. Exit Criteria
- Phase 08 标记 DONE
- current_phase 切换到 Phase 09 蓝图

---

## 6. Execution Progress

- [x] 08D-WP1 端到端联调脚本固化：
  - 新增 `infra/scripts/verify_phase08_integration.py`
  - 覆盖多角色场景、数据边界过滤、跨租户拒绝语义、审计导出证据链
- [x] 08D-WP2 Phase 09 输入清单：
  - 新增 `docs/ops/PHASE09_READINESS_CHECKLIST.md`
  - 明确数据模型/API/测试与门禁基线输入
- [x] 08D-WP3 下一阶段蓝图准备：
  - 新增 `phases/phase-09-flight-resource-asset-management.md`
  - 更新 `phases/index.md` 执行顺序，纳入 Phase 09
- [x] 08D-WP4 门禁复验与关账：
  - 已通过：
    - `docker compose -f infra/docker-compose.yml run --rm --build app ruff check app tests infra/scripts`
    - `docker compose -f infra/docker-compose.yml run --rm --build app mypy app`
    - `docker compose -f infra/docker-compose.yml run --rm --build app pytest -q`
    - `docker compose -f infra/docker-compose.yml up --build -d`
    - `docker compose -f infra/docker-compose.yml run --rm --build app alembic upgrade head`
    - `docker compose -f infra/docker-compose.yml run --rm --build app-tools python -m app.infra.openapi_export`
    - `docker compose -f infra/docker-compose.yml run --rm --build -e APP_BASE_URL=http://app:8000 app-tools python infra/scripts/demo_e2e.py`
    - `docker compose -f infra/docker-compose.yml run --rm --build -e APP_BASE_URL=http://app:8000 app-tools python infra/scripts/verify_smoke.py`
  - 已通过（08D 核心集成验收）：
    - `docker compose -f infra/docker-compose.yml run --rm --build -e APP_BASE_URL=http://app:8000 app-tools python infra/scripts/verify_phase08_integration.py`
  - 历史阻塞（已解除）：
    - `docker compose -f infra/docker-compose.yml run --rm --build -e APP_BASE_URL=http://app:8000 app-tools python infra/scripts/verify_phase08_integration.py`
    - 曾出现错误：`open //./pipe/dockerDesktopLinuxEngine: Access is denied`
    - 2026-02-24T16:49:45Z 复验：按协议执行立即重试（单次重试 + 3 次循环重试），仍被 npipe 拒绝（镜像探测 `redis:7-alpine` / `postgis/postgis:16-3.4` 均失败）
    - 2026-02-24T17:11:28Z 复验：用户要求继续后再次执行 `docker info` + 同命令立即重试，仍被 npipe 拒绝（`postgis/postgis:16-3.4` / `redis:7-alpine`）
    - 2026-02-24T17:29:50Z 复验通过：修复集成脚本的 approval 路径与审计读取策略，并补齐 audit middleware 对 `-export`/显式上下文读请求的审计覆盖后，同命令一次通过。
