# Resume Protocol (Autonomous)

## Restart Entry (Read First)
This file is the single restart entrypoint. On every fresh Codex session, read files in this order:
1. `governance/AGENTS.md`
2. `governance/00_INDEX.md`
3. `governance/01_GOVERNANCE.md`
4. `governance/02_REPO_LAYOUT.md`
5. `governance/03_PHASE_LIFECYCLE.md`
6. `governance/04_CHAT_INTERACTION_PROTOCOL.md`
7. `governance/ROADMAP.md`
8. `项目最终目标.md`
9. `phases/state.md`
10. `docs/PROJECT_STATUS.md`
11. `phases/index.md`
12. `logs/PROGRESS.md`
13. `phases/phase-08-one-net-unified-flight-planning.md`
14. `phases/phase-08a-org-rbac-foundation.md`
15. `phases/phase-08b-data-perimeter-policy.md`
16. `phases/phase-08c-audit-hardening.md`
17. `phases/phase-08d-integration-acceptance.md`
18. `phases/phase-09-flight-resource-asset-management.md`
19. `phases/phase-10-unified-map-situation-v1.md`
20. `phases/phase-11-unified-task-center-workflow.md`
21. `phases/phase-12-airspace-compliance-safety-rails.md`
22. `phases/phase-13-data-outcomes-alert-closure.md`
23. `phases/phase-14-ai-assistant-evidence-chain.md`
24. `phases/phase-15-kpi-open-platform.md`
25. `phases/phase-16-saas-console-ui.md`
26. `phases/phase-17-multi-org-data-perimeter-v2.md`
27. `phases/phase-18-outcomes-repository-object-storage.md`
28. `phases/phase-19-real-device-video-integration.md`
29. `phases/phase-20-task-center-v2-optimization.md`
30. `phases/phase-21-airspace-compliance-hub-v2.md`
31. `phases/phase-22-alert-oncall-notification-v2.md`
32. `phases/phase-23-ai-model-governance-v2.md`
33. `phases/phase-24-billing-quota-system.md`
34. `phases/phase-25-observability-reliability.md`
35. `phases/phase-26-ui-information-architecture-design-system.md`
36. `phases/phase-27-operations-ui-workflow-closure.md`
37. `phases/phase-28-compliance-alert-operations-workbench.md`
38. `phases/phase-29-data-ai-governance-ui.md`
39. `phases/phase-30-commercial-platform-ops-ui.md`
40. `phases/phase-31-observability-reliability-ops-console.md`
41. `phases/phase-32-role-workbench-productization.md`
42. `phases/phase-33-one-map-command-center-v2.md`
43. `phases/phase-34-guided-task-workflow-usability.md`
44. `phases/phase-35-mobile-field-operations.md`
45. `phases/phase-36-business-closure-outcomes-consumption.md`
46. `phases/phase-37-notification-collaboration-hub.md`
47. `phases/phase-38-delivery-onboarding-operations.md`
48. `phases/phase-39-release-adoption-lifecycle.md`

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
- updated_at_utc: `2026-03-02T05:06:26.0016159Z`
- current_phase: `DONE`
- phase_status: `DONE`
- last_success_phase: `phase-39-release-adoption-lifecycle.md`
- current_focus: `Phase 39 is closed; 39-WP1..39-WP6 extended /ui/platform into a release-adoption console with release checks, help center, release notes, and gray-enable guidance. There is no active phase checkpoint now.`

## Next TODO (Execution Target)
1. No active execution phase. Wait for a new blueprint before moving the checkpoint out of `DONE`.
2. Reuse the Docker Compose regression checklist below for any future changes.
3. Use `phases/state.md` as the execution SSOT; do not reopen completed phases unless explicitly requested.
4. Keep all future UI changes at or above the Phase 32 productization baseline; do not allow UX regressions.

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
- `docker compose -f infra/docker-compose.yml run --rm --build -e APP_BASE_URL=http://app:8000 app-tools python infra/scripts/verify_phase08_integration.py`
- `docker compose -f infra/docker-compose.yml run --rm --build -e APP_BASE_URL=http://app:8000 app-tools python infra/scripts/demo_phase25_observability_reliability.py`
- `docker compose -f infra/docker-compose.yml run --rm --build -e APP_BASE_URL=http://app:8000 app-tools python infra/scripts/demo_phase29_data_ai_governance_ui.py`
- `docker compose -f infra/docker-compose.yml run --rm --build -e APP_BASE_URL=http://app:8000 app-tools python infra/scripts/demo_phase30_commercial_platform_ops_ui.py`
- `docker compose -f infra/docker-compose.yml run --rm --build -e APP_BASE_URL=http://app:8000 app-tools python infra/scripts/demo_phase31_observability_reliability_ops_console.py`

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
`先读取 phases/resume.md 和 phases/state.md。当前 current_phase=DONE，status=DONE，last_success_phase=phase-39-release-adoption-lifecycle.md；Phase 39 已完成并关账，所有既定阶段已闭环，如需继续请先提供新的阶段蓝图。`
