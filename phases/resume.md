# Resume Protocol (Autonomous)

## Restart Entry (Read First)
This file is the single restart entrypoint. On every fresh Codex session, read files in this order:
1. `AGENTS.md`
2. `governance/AGENTS.md`
3. `governance/00_INDEX.md`
4. `governance/01_GOVERNANCE.md`
5. `governance/02_REPO_LAYOUT.md`
6. `governance/03_PHASE_LIFECYCLE.md`
7. `governance/04_CHAT_INTERACTION_PROTOCOL.md`
8. `governance/ROADMAP.md`
9. `phases/state.md`
10. `docs/PROJECT_STATUS.md`
11. `phases/index.md`
12. `logs/PROGRESS.md`
13. `phases/phase-07c-tenant-export-purge.md`

Optional when tenant-boundary scope is active:
- `governance/tenant_boundary_matrix.md`

## Current Snapshot
- updated_at_utc: `2026-02-24T12:46:47Z`
- current_phase: `DONE`
- phase_status: `DONE`
- last_success_phase: `phase-07c-tenant-export-purge.md`
- current_focus: `07C completed; full gate chain rerun passed via Docker Compose`

## Next TODO (Execution Target)
1. No pending TODO in current `phases/index.md` execution chain (01..07C complete).
2. Wait for next blueprint update (e.g., new phase file + index/state change) before implementation.
3. Keep Docker Compose gate commands below as baseline regression checklist.

## Quality Gate Commands
Use Docker Compose commands directly in this environment:
- `docker compose -f infra/docker-compose.yml run --rm --build app ruff check app tests infra/scripts`
- `docker compose -f infra/docker-compose.yml run --rm --build app mypy app`
- `docker compose -f infra/docker-compose.yml run --rm --build app pytest -q`
- `docker compose -f infra/docker-compose.yml up --build -d`
- `docker compose -f infra/docker-compose.yml run --rm --build app alembic upgrade head`
- `docker compose -f infra/docker-compose.yml run --rm --build app-tools python -m app.infra.openapi_export`
- `docker compose -f infra/docker-compose.yml run --rm --build -e APP_BASE_URL=http://app:8000 app-tools python infra/scripts/demo_e2e.py`
- `docker compose -f infra/docker-compose.yml run --rm --build -e APP_BASE_URL=http://app:8000 app-tools python infra/scripts/verify_smoke.py`

## Copy-Paste Prompt For Next Session
`先读取 phases/resume.md 和 phases/state.md。若 current_phase=DONE，则仅执行回归门禁并等待下一阶段蓝图；若不是 DONE，则按 Next TODO 继续并同步 state/project_status/progress。`
