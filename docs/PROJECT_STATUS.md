# PROJECT_STATUS.md
# 项目状态（同步视图 / Mirrored Status）

> 用途：提供面向阅读者的当前状态摘要，与执行状态文件保持同步。
> Rule: 更新必须可被门禁验证（ruff/mypy/pytest/e2e/grep/文件存在性）。
> Execution SSOT: `phases/state.md`

## 1. Current Focus（当前焦点）
- Current Phase: phase-12-airspace-compliance-safety-rails.md (READY; from phases/state.md)
- Current Sub-Phase / Blueprint: Phase 11 closed as DONE (`11-WP1`..`11-WP4`)
- Next Target: execute phase-12 P0 (`12-WP1/12-WP3-min-guardrails`)

## 2. Gate Status（门禁状态）
> 最近一次门禁结果（必须可复现）
> Last verified at (UTC): 2026-02-25T04:15:26Z
> Note: host `make` is unavailable in current environment; equivalent Docker Compose commands were executed directly.
> WIP note (2026-02-25T04:15:26Z): Phase 11 closed as DONE after completing P1/P2 enhancements and WP4 closeout (`demo_phase11_task_center` + full gate rerun).

- ruff: PASS (`docker compose ... app ruff check app tests infra/scripts`)
- mypy: PASS (60 source files)
- pytest: PASS (`docker compose ... app pytest -q`)
- e2e: PASS (`demo_e2e.py` + `verify_smoke.py`)
- phase08 integration: PASS (`verify_phase08_integration.py`)
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
  - docker compose -f infra/docker-compose.yml run --rm --build -e APP_BASE_URL=http://app:8000 app-tools python infra/scripts/verify_phase08_integration.py

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
- phase-08-one-net-unified-flight-planning.md: DONE (planning blueprint)
- phase-08a-org-rbac-foundation.md: DONE
- phase-08b-data-perimeter-policy.md: DONE
- phase-08c-audit-hardening.md: DONE
- phase-08d-integration-acceptance.md: DONE
- phase-09-flight-resource-asset-management.md: DONE
- phase-10-unified-map-situation-v1.md: DONE
- phase-11-unified-task-center-workflow.md: DONE

## 4.1 Supplemental Progress Notes（补充进展）
> 非 checkpoint 条目，仅作日志参考，不覆盖 phases/state.md。
- 07B B1/B2/B3 migrations are present: `202602230014`..`202602230022`.
- 07B B4 migrations are present: `202602240023`..`202602240025`.
- 07B B5 migrations are present: `202602240026`..`202602240028` (reporting/compliance approval boundary landed).
- 07C-1 tenant export artifacts are present: `app/services/tenant_export_service.py`, `app/api/routers/tenant_export.py`, `tests/test_tenant_export.py`, `docs/ops/TENANT_EXPORT.md`.
- 07C-2/07C-3 artifacts are present: `app/services/tenant_purge_service.py`, `app/api/routers/tenant_purge.py`, `tests/test_tenant_purge_dry_run.py`, `tests/test_tenant_purge_execute.py`, `docs/ops/TENANT_PURGE.md`.
- 08C audit hardening artifacts are present: `app/infra/audit.py`, `app/api/routers/identity.py`, `app/services/identity_service.py`, `tests/test_identity.py` (policy-change/cross-tenant-deny/batch-authorization audit coverage).
- 08D integration artifacts are present: `infra/scripts/verify_phase08_integration.py`, `docs/ops/PHASE09_READINESS_CHECKLIST.md`, `phases/phase-09-flight-resource-asset-management.md`.
- 09-WP1 asset ledger artifacts are present: `app/domain/models.py` (`Asset*` models), `app/services/asset_service.py`, `app/api/routers/asset.py`, migration chain `202602240035/036/037`, `tests/test_asset.py`.
- 09-WP2 availability/health artifacts are present: `AssetAvailabilityStatus/AssetHealthStatus`, API `POST /api/assets/{id}/availability`, `POST /api/assets/{id}/health`, `GET /api/assets/pool`, migration chain `202602240038/039/040`, and WP2 regression coverage in `tests/test_asset.py`.
- 09-WP3 maintenance artifacts are present: `AssetMaintenanceWorkOrder/AssetMaintenanceHistory`, API `/api/assets/maintenance/workorders*`, migration chain `202602240041/042/043`, and workflow regression coverage in `tests/test_asset_maintenance.py`.
- 09-WP4 closeout artifacts are present: `GET /api/assets/pool/summary`, `infra/scripts/demo_phase09_resource_pool_maintenance.py`, `logs/phase-09-flight-resource-asset-management.md.report.md`.
- 10-WP1/WP2/WP3 artifacts are present: `app/services/map_service.py`, `app/api/routers/map_router.py`, map DTOs in `app/domain/models.py`, command-center one-map UI updates (`app/web/templates/command_center.html`, `app/web/static/command_center.js`), and regression coverage `tests/test_map.py`.
- 11-WP1/WP2/WP3 artifacts are present: `app/services/task_center_service.py`, `app/api/routers/task_center.py`, task-center DTOs/models in `app/domain/models.py`, migration chain `202602240044/045/046`, regression coverage `tests/test_task_center.py`, and phase demo `infra/scripts/demo_phase11_task_center.py`.

## 5. Audit Log（自动审计记录）
> 每次“自动关账/推进”都追加一条。失败也要写入 logs/ 下报告。

- 2026-02-25T04:15:26Z (UTC): Phase 11 closed as DONE. Completed P1/P2 capabilities (auto-dispatch scoring explainability, risk/checklist update, attachment/comment collaboration), delivered demo script `infra/scripts/demo_phase11_task_center.py`, generated report `logs/phase-11-unified-task-center-workflow.md.report.md`, and passed full closeout chain (`ruff`, `mypy`, `pytest -q`, `up --build -d`, `alembic upgrade head`, OpenAPI export, `demo_e2e`, `verify_smoke`, `demo_phase11_task_center`).
- 2026-02-25T03:56:32Z (UTC): Phase 11 moved to RUNNING and delivered P0 baseline (`11-WP1`, `11-WP2` manual dispatch minimal chain, `11-WP3` core lifecycle state machine). Added task-center domain/service/router/migrations (`202602240044/045/046`) and regression coverage (`tests/test_task_center.py`). Verification passed via Docker Compose (`ruff check app tests infra/scripts`, `mypy app`, `pytest -q`, `alembic upgrade head`).
- 2026-02-25T03:40:43Z (UTC): Phase 10 closed as DONE. Completed WP4 closeout with acceptance demo script `infra/scripts/demo_phase10_one_map.py` and report `logs/phase-10-unified-map-situation-v1.md.report.md`; full gate chain passed (`ruff`, `mypy`, `pytest -q`, `alembic upgrade head`, OpenAPI export, `demo_e2e`, `verify_smoke`, `demo_phase10_one_map`). Checkpoint advanced to `phase-11-unified-task-center-workflow.md` with `READY`.
- 2026-02-25T03:36:43Z (UTC): Phase 10 WP3 completed. Enhanced `/ui/command-center` with layer toggles, track replay controls, alert highlight panel, and video-slot placeholder abstraction; wired UI to `/api/map/*` while keeping `ws/dashboard` stats stream. Verification passed via Docker Compose (`ruff check app tests infra/scripts`, `mypy app`, `pytest -q`).
- 2026-02-24T19:06:22Z (UTC): Phase 10 moved into active implementation (`RUNNING`). Completed P0 work packages `10-WP1/10-WP2`: added map aggregation service (`app/services/map_service.py`), map APIs (`/api/map/overview`, `/api/map/layers/{resources|tasks|alerts|events}`, `/api/map/tracks/replay`), model DTOs, and regression coverage (`tests/test_map.py`). Verification passed via Docker Compose: `ruff check app tests infra/scripts`, `mypy app`, `pytest -q`.
- 2026-02-24T18:53:40Z (UTC): Priority tuning completed for `phase-10`..`phase-15` blueprints. Added explicit `P0/P1/P2` sequencing sections and standardized execution order (`P0 -> P1 -> P2 -> WP4`) to reduce implementation risk and keep non-blocking features deferrable.
- 2026-02-24T18:49:21Z (UTC): Added phase blueprints `phase-10`..`phase-15`, updated `phases/index.md` execution order, and switched checkpoint from `DONE` to `current_phase=phase-10-unified-map-situation-v1.md` with `status=READY` for next implementation cycle.
- 2026-02-24T18:25:07Z (UTC): Phase 09 closed as DONE (WP1-WP4 complete). Added regional resource pool summary API (`GET /api/assets/pool/summary`) and acceptance demo script (`infra/scripts/demo_phase09_resource_pool_maintenance.py`), then passed full baseline Docker Compose gates (`ruff`, `mypy`, `pytest -q`, `alembic upgrade head`, OpenAPI export, `demo_e2e`, `verify_smoke`, `verify_phase08_integration.py`, phase09 demo). Report generated at `logs/phase-09-flight-resource-asset-management.md.report.md`; checkpoint switched to `DONE`.
- 2026-02-24T18:11:32Z (UTC): Phase 09 WP3 completed (maintenance workorder/history model + APIs + explicit audit action contexts + migration chain `202602240041/042/043` + `tests/test_asset_maintenance.py`). Baseline Docker Compose gates passed: `ruff`, `mypy`, `pytest -q`, `alembic upgrade head`, OpenAPI export, `demo_e2e`, `verify_smoke`, and `verify_phase08_integration.py`.
- 2026-02-24T18:01:57Z (UTC): Phase 09 WP2 completed (asset availability/health model + pool query APIs + migration chain `202602240038/039/040` + WP2 tests in `tests/test_asset.py`). Baseline Docker Compose gates passed: `ruff`, `mypy`, `pytest -q`, `alembic upgrade head`, OpenAPI export, `demo_e2e`, `verify_smoke`.
- 2026-02-24T17:42:16Z (UTC): Phase 09 WP1 completed (asset ledger model + migration chain `202602240035/036/037` + minimal `/api/assets` APIs + tenant-boundary/lifecycle/event tests). Baseline Docker Compose gates passed: `ruff`, `mypy`, `pytest -q`, `alembic upgrade head`, OpenAPI export, `demo_e2e`, `verify_smoke`.
- 2026-02-24T17:33:59Z (UTC): Phase 09 set to RUNNING. Added executable WP breakdown (WP1-WP4) in `phases/phase-09-flight-resource-asset-management.md`; current focus moved to WP1 asset-ledger schema/migration/API/tests.
- 2026-02-24T17:29:50Z (UTC): Phase 08D closed as DONE. Re-ran `verify_phase08_integration.py` to PASS after fixing integration-script approval path (`/api/approvals/audit-export`), switching script evidence assertion to DB-backed audit log reads, and hardening audit middleware read capture (`-export` + explicit audit context on reads). Checkpoint advanced to `phase-09-flight-resource-asset-management.md` with `READY`; report generated at `logs/phase-08d-integration-acceptance.md.report.md`.
- 2026-02-24T17:11:28Z (UTC): After user requested to continue, rechecked `docker info` and retried `verify_phase08_integration.py` with immediate retry. Both attempts still failed with npipe denial (`open //./pipe/dockerDesktopLinuxEngine: Access is denied`; image probe failures on `postgis/postgis:16-3.4` and `redis:7-alpine`), phase 08D remains `RUNNING`.
- 2026-02-24T16:49:45Z (UTC): Re-ran `verify_phase08_integration.py` with immediate retry policy (single retry + 3-loop retry); all attempts failed with Docker npipe access denial (`open //./pipe/dockerDesktopLinuxEngine: Access is denied`, image probe on `redis:7-alpine` / `postgis/postgis:16-3.4`), so phase 08D remains `RUNNING`.
- 2026-02-24T16:15:08Z (UTC): Phase 08D moved to RUNNING; integration assets landed (Phase 08 integration script + Phase 09 readiness checklist + Phase 09 blueprint + index update). Baseline gate/e2e commands passed, but `verify_phase08_integration.py` command is currently blocked by intermittent Docker npipe access denial (`open //./pipe/dockerDesktopLinuxEngine: Access is denied`).
- 2026-02-24T16:01:53Z (UTC): Phase 08C closed as DONE (audit middleware schema standardization + export/download read audit coverage + identity policy-change/cross-tenant-deny/batch-bind hardening + regressions/docs); full gate chain passed (`ruff`, `mypy`, `pytest -q`, `up --build -d`, `alembic upgrade head`, OpenAPI export, `demo_e2e`, `verify_smoke`); checkpoint advanced to `phase-08d-integration-acceptance.md` with `READY`.
- 2026-02-24T15:41:00Z (UTC): Phase 08C moved to RUNNING; implemented audit hardening for policy changes, cross-tenant deny semantics, and batch authorization (`POST /api/identity/users/{user_id}/roles:batch-bind`), plus standardized audit detail fields in middleware; gate rerun attempted but blocked by Docker daemon permission (`open //./pipe/dockerDesktopLinuxEngine: Access is denied`).
- 2026-02-24T15:27:01Z (UTC): Phase 08B closed as DONE (policy model + migration chain `202602240032/033/034` + core-domain query perimeter integration + identity policy APIs + regression tests); full gates passed (`alembic upgrade head`, `ruff`, `mypy`, `pytest -q`, `demo_e2e`, `verify_smoke`); checkpoint moved to `phase-08c-audit-hardening.md` with `READY`.
- 2026-02-24T14:47:12Z (UTC): Phase 08A closed as DONE (WP1-WP4 complete); full gate chain passed (`up --build -d`, `alembic upgrade head` to `202602240031`, `ruff`, `mypy`, `pytest -q`, `demo_e2e`, `verify_smoke`); checkpoint moved to `phase-08b-data-perimeter-policy.md` with `READY`.
- 2026-02-24T14:39:55Z (UTC): Phase 08A WP2 landed (role template DTO/service/API/tests), targeted checks passed (`pytest tests/test_identity.py tests/test_identity_org.py -q`, targeted `ruff`, targeted `mypy`).
- 2026-02-24T22:34:22Z (UTC): Phase 08A moved to RUNNING; WP1 completed (org models + migrations `202602240029/030/031` + `tests/test_identity_org.py` pass).
- 2026-02-24T22:23:14Z (UTC): Phase 08A blueprint detailed to executable WP1-WP4 (schema/service/api/tests + migration strategy + acceptance matrix).
- 2026-02-24T22:09:48Z (UTC): phase decomposition completed (`08A/08B/08C/08D`), checkpoint moved to `current_phase=phase-08a-org-rbac-foundation.md`, status `READY`.
- 2026-02-24T22:06:53Z (UTC): execution checkpoint switched to `READY` with `current_phase=phase-08-one-net-unified-flight-planning.md`.
- 2026-02-24T11:00:44Z (UTC): quality gates rerun passed via Docker Compose (`ruff`, `mypy`, `pytest`, `alembic upgrade head`, OpenAPI generation, e2e demo scripts, `verify_smoke`).
- 2026-02-24T11:23:20Z (UTC): quality gates rerun passed via Docker Compose (`ruff`, `mypy`, `pytest -q`, `alembic upgrade head` to `202602240025`, OpenAPI generation, `demo_e2e`, `verify_smoke`).
- 2026-02-24T12:07:43Z (UTC): 07B B5 landed (`202602240026`/`202602240027`/`202602240028`) and gates rerun passed via Docker Compose (`ruff`, `mypy`, `pytest -q`, `alembic upgrade head`, OpenAPI generation, `demo_e2e`, `verify_smoke`).
- 2026-02-24T12:22:51Z (UTC): 07C-2/07C-3 code landed, but gate rerun blocked by Docker daemon permission (`permission denied while trying to connect to npipe:////./pipe/dockerDesktopLinuxEngine`).
- 2026-02-24T12:46:47Z (UTC): 07C full gate chain rerun passed (`ruff`, `mypy`, `pytest -q`, `alembic upgrade head`, OpenAPI generation, `demo_e2e`, `verify_smoke`); phase marked DONE.

