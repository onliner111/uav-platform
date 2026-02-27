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
26. `phases/phase-16-saas-console-ui.md`
27. `phases/phase-17-multi-org-data-perimeter-v2.md`
28. `phases/phase-18-outcomes-repository-object-storage.md`
29. `phases/phase-19-real-device-video-integration.md`
30. `phases/phase-20-task-center-v2-optimization.md`
31. `phases/phase-21-airspace-compliance-hub-v2.md`
32. `phases/phase-22-alert-oncall-notification-v2.md`
33. `phases/phase-23-ai-model-governance-v2.md`
34. `phases/phase-24-billing-quota-system.md`
35. `phases/phase-25-observability-reliability.md`

Optional when tenant-boundary scope is active:
- `governance/tenant_boundary_matrix.md`

## File Read Encoding Rule (Mandatory)
- When reading local text/markdown files in PowerShell, always use UTF-8 explicitly:
- `Get-Content <file> -Encoding utf8`
- Do not rely on default encoding for `Get-Content`.
- This rule is persistent and must be applied on every restarted session.

## File Write Encoding Rule (Mandatory)
- When writing local text/markdown files in PowerShell, always use UTF-8 explicitly:
- `Set-Content <file> -Encoding utf8`
- `Out-File <file> -Encoding utf8`
- `Add-Content <file> -Encoding utf8`
- Do not use `>` or `>>` redirection to write markdown/text files.
- In markdown documentation command examples, avoid `>` / `>>` write patterns; prefer `Out-File -Encoding utf8`.
- This rule is persistent and must be applied on every restarted session.

## Current Snapshot
- updated_at_utc: `2026-02-26T19:51:06Z`
- current_phase: `phase-19-real-device-video-integration.md`
- phase_status: `READY`
- last_success_phase: `phase-18-outcomes-repository-object-storage.md`
- current_focus: `Phase 18 is DONE (18-WP1..18-WP6 closed with full gates); next phase is Phase 19 and awaits start`

## Next TODO (Execution Target)
1. Start Phase 19 from P0 and execute in order `P0 -> P1 -> P2 -> 19-WP6`, keeping full gate pass as closeout condition.
2. Keep Docker Compose baseline gate commands below as regression checklist for each new phase.
3. Continue to enforce intra-phase auto-continue rule (`P0 -> P1 -> P2 -> WP6`) for all future phases.

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
`先读取 phases/resume.md 和 phases/state.md。当前 status=READY，current_phase=phase-19-real-device-video-integration.md；启动并执行 Phase 19（P0 -> P1 -> P2 -> 19-WP6），通过全量门禁后关账并停止。`
