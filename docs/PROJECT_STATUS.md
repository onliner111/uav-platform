# PROJECT_STATUS.md
# 项目状态（同步视图 / Mirrored Status）

> 用途：提供面向阅读者的当前状态摘要，与执行状态文件保持同步。
> Rule: 更新必须可被门禁验证（ruff/mypy/pytest/e2e/grep/文件存在性）。
> Execution SSOT: `phases/state.md`

## 1. Current Focus（当前焦点）
- Current Phase: DONE (phase-07c-tenant-export-purge.md completed; from phases/state.md)
- Current Sub-Phase / Blueprint: 07C-1/07C-2/07C-3 accepted; full quality gate chain passed
- Next Target: wait for next phase blueprint after current index completion

## 2. Gate Status（门禁状态）
> 最近一次门禁结果（必须可复现）
> Last verified at (UTC): 2026-02-24T12:46:47Z
> Note: host `make` is unavailable in current environment; equivalent Docker Compose commands were executed directly.

- ruff: PASS (`docker compose ... app ruff check app tests infra/scripts`)
- mypy: PASS (53 source files)
- pytest: PASS (`docker compose ... app pytest -q`)
- e2e: PASS (`demo_e2e.py` + `verify_smoke.py`)
- alembic head: PASS (`docker compose ... app alembic upgrade head`)

## 3. Evidence（证据 / 可复现命令）
> 所有结论必须能用这些命令复现

### Lint / Type / Test（Docker Compose）
- ruff:
  - docker compose -f infra/docker-compose.yml run --rm --build app ruff check app tests infra/scripts
- mypy:
  - docker compose -f infra/docker-compose.yml run --rm --build app mypy app
- pytest:
  - docker compose -f infra/docker-compose.yml run --rm --build app pytest -q
- e2e（如存在）:
  - docker compose -f infra/docker-compose.yml up --build -d
  - docker compose -f infra/docker-compose.yml run --rm --build app alembic upgrade head
  - docker compose -f infra/docker-compose.yml run --rm --build app-tools python -m app.infra.openapi_export
  - docker compose -f infra/docker-compose.yml run --rm --build -e APP_BASE_URL=http://app:8000 app-tools python infra/scripts/demo_e2e.py
  - docker compose -f infra/docker-compose.yml run --rm --build -e APP_BASE_URL=http://app:8000 app-tools python infra/scripts/verify_smoke.py

## 4. Completed Phases（已完成阶段）
> 只记录“通过门禁”的阶段；每条必须带 revision / 时间 / 证据
> Authoritative source: phases/state.md (execution SSOT), corroborated by logs/PROGRESS.md.

- phase-01-inspection.md: DONE
- phase-02-defect-closure.md: DONE
- phase-03-emergency.md: DONE
- phase-04-command-center.md: DONE
- phase-05-compliance.md: DONE
- phase-06-reporting.md: DONE
- phase-07a-identity-preview.md: DONE
- phase-07a-core-batch-a.md: DONE
- phase-07a-lookup-hardening-execution-plan.md: DONE
- phase-07b-db-boundary-master.md: DONE
- phase-07c-tenant-export-purge.md: DONE

## 4.1 Supplemental Progress Notes（补充进展）
> 非 checkpoint 条目，仅作日志参考，不覆盖 phases/state.md。
- 07B B1/B2/B3 migrations are present: `202602230014`..`202602230022`.
- 07B B4 migrations are present: `202602240023`..`202602240025`.
- 07B B5 migrations are present: `202602240026`..`202602240028` (reporting/compliance approval boundary landed).
- 07C-1 tenant export artifacts are present: `app/services/tenant_export_service.py`, `app/api/routers/tenant_export.py`, `tests/test_tenant_export.py`, `docs/ops/TENANT_EXPORT.md`.
- 07C-2/07C-3 artifacts are present: `app/services/tenant_purge_service.py`, `app/api/routers/tenant_purge.py`, `tests/test_tenant_purge_dry_run.py`, `tests/test_tenant_purge_execute.py`, `docs/ops/TENANT_PURGE.md`.

## 5. Audit Log（自动审计记录）
> 每次“自动关账/推进”都追加一条。失败也要写入 logs/ 下报告。

- 2026-02-24T11:00:44Z (UTC): quality gates rerun passed via Docker Compose (`ruff`, `mypy`, `pytest`, `alembic upgrade head`, OpenAPI generation, e2e demo scripts, `verify_smoke`).
- 2026-02-24T11:23:20Z (UTC): quality gates rerun passed via Docker Compose (`ruff`, `mypy`, `pytest -q`, `alembic upgrade head` to `202602240025`, OpenAPI generation, `demo_e2e`, `verify_smoke`).
- 2026-02-24T12:07:43Z (UTC): 07B B5 landed (`202602240026`/`202602240027`/`202602240028`) and gates rerun passed via Docker Compose (`ruff`, `mypy`, `pytest -q`, `alembic upgrade head`, OpenAPI generation, `demo_e2e`, `verify_smoke`).
- 2026-02-24T12:22:51Z (UTC): 07C-2/07C-3 code landed, but gate rerun blocked by Docker daemon permission (`permission denied while trying to connect to npipe:////./pipe/dockerDesktopLinuxEngine`).
- 2026-02-24T12:46:47Z (UTC): 07C full gate chain rerun passed (`ruff`, `mypy`, `pytest -q`, `alembic upgrade head`, OpenAPI generation, `demo_e2e`, `verify_smoke`); phase marked DONE.

