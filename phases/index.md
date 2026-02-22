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
3. Execute phase 1
4. Verify
5. If success → automatically continue to next phase
6. Repeat until all phases complete

---

## Output Policy

After completing all phases:

Output:

- Completed Phases Summary
- Final Verification Commands
- Any Known Risks
