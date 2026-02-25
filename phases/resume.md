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
9. `项目最终目标.md`
10. `phases/state.md`
11. `docs/PROJECT_STATUS.md`
12. `phases/index.md`
13. `logs/PROGRESS.md`
14. `phases/phase-08-one-net-unified-flight-planning.md`
15. `phases/phase-08a-org-rbac-foundation.md`
16. `phases/phase-08b-data-perimeter-policy.md`
17. `phases/phase-08c-audit-hardening.md`
18. `phases/phase-08d-integration-acceptance.md`
19. `phases/phase-09-flight-resource-asset-management.md`
20. `phases/phase-10-unified-map-situation-v1.md`
21. `phases/phase-11-unified-task-center-workflow.md`
22. `phases/phase-12-airspace-compliance-safety-rails.md`
23. `phases/phase-13-data-outcomes-alert-closure.md`
24. `phases/phase-14-ai-assistant-evidence-chain.md`
25. `phases/phase-15-kpi-open-platform.md`

Optional when tenant-boundary scope is active:
- `governance/tenant_boundary_matrix.md`

## Current Snapshot
- updated_at_utc: `2026-02-25T06:03:33Z`
- current_phase: `phase-15-kpi-open-platform.md`
- phase_status: `DONE`
- last_success_phase: `phase-15-kpi-open-platform.md`
- current_focus: `All indexed phases (01..15) are closed as DONE; repository is at full-roadmap completion checkpoint`

## Next TODO (Execution Target)
1. Keep Docker Compose baseline gate commands below as regression checklist for new roadmap items.
2. If new phases are added, update `phases/index.md` and restart from `phases/state.md`.
3. Continue to enforce intra-phase auto-continue rule (`P0 -> P1 -> P2 -> WP4`) for any future phases.

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

## Docker Permission Rule (Mandatory)
- For all Docker-related quality-gate commands in this environment, run with escalated permissions by default.
- If any Docker command returns npipe access denial (e.g. `permission denied ... dockerDesktopLinuxEngine`), immediately retry the same command with escalated permissions in the same turn.
- This rule is persistent and must be applied on every restarted session.

## Intra-Phase Auto-Continue Rule (Mandatory)
- Within current phase, execute small stages continuously in declared order (for example `P0 -> P1 -> P2 -> WP4`).
- If a small stage passes checks, immediately continue to the next small stage without asking.
- Only stop for hard blockers or when the whole phase is completed.
- This rule is persistent and must be applied on every restarted session.

## Copy-Paste Prompt For Next Session
`先读取 phases/resume.md 和 phases/state.md。当前 status=DONE（phase-15 已完成）；如有新增阶段，请先更新 phases/index.md 与 phases/state.md 后继续执行。`
