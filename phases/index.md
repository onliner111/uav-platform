# Phase Execution Index — Autonomous Mode

本文件定义阶段执行顺序。

Codex MUST execute phases sequentially.

---

## Execution Order

1. phase-01-inspection.md
2. phase-02-defect-closure.md
3. phase-03-emergency.md
4. phase-04-command-center.md
5. phase-05-compliance.md
6. phase-06-reporting.md
7. phase-07-master-blueprint.md
8. phase-07-tenant-boundary.md
9. phase-07a-identity-preview.md
10. phase-07a-core-batch-a.md
11. phase-07a-lookup-hardening-analysis.md
12. phase-07a-lookup-hardening-execution-plan.md
13. phase-07b-db-boundary-master.md
14. phase-07c-tenant-export-purge.md
15. phase-08-one-net-unified-flight-planning.md
16. phase-08a-org-rbac-foundation.md
17. phase-08b-data-perimeter-policy.md
18. phase-08c-audit-hardening.md
19. phase-08d-integration-acceptance.md
20. phase-09-flight-resource-asset-management.md
21. phase-10-unified-map-situation-v1.md
22. phase-11-unified-task-center-workflow.md
23. phase-12-airspace-compliance-safety-rails.md
24. phase-13-data-outcomes-alert-closure.md
25. phase-14-ai-assistant-evidence-chain.md
26. phase-15-kpi-open-platform.md
27. phase-16-saas-console-ui.md
28. phase-17-multi-org-data-perimeter-v2.md
29. phase-18-outcomes-repository-object-storage.md
30. phase-19-real-device-video-integration.md
31. phase-20-task-center-v2-optimization.md
32. phase-21-airspace-compliance-hub-v2.md
33. phase-22-alert-oncall-notification-v2.md
34. phase-23-ai-model-governance-v2.md
35. phase-24-billing-quota-system.md
36. phase-25-observability-reliability.md

---

## Execution Rules

- MUST complete one phase fully before starting next.
- MUST ensure Quality Gate passes before moving forward:
  - make lint
  - make typecheck
  - make test
  - make e2e (if exists)
- MUST stop if a phase fails after 3 fix cycles.
- MUST NOT skip phases.
- MUST NOT reorder phases.
- MUST start from `phases/state.md -> current_phase`.
- MUST execute intra-phase small stages sequentially and auto-continue:
  - if a small stage passes checks, immediately proceed to the next small stage
  - continue until the whole phase is DONE or blocked by hard failure policy

---

## Phase Transition Criteria

Before moving to next phase:

- All Acceptance Criteria of current phase satisfied
- All tests green
- Demo script works
- No breaking change to previous features

---

## Autonomous Execution Instruction

Codex should:

1. Read governance/AGENTS.md
2. Read phases/index.md
3. Read phases/state.md
4. Execute from current_phase
5. Verify
6. If success → automatically continue to next phase
7. Repeat until all phases complete

---

## Output Policy

After completing all phases:

Output:

- Completed Phases Summary
- Final Verification Commands
- Any Known Risks
