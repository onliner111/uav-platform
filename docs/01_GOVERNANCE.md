# 01_GOVERNANCE.md - Documentation Governance

## 1. Single Source of Truth (SSOT) Mapping

| Governance Area | SSOT File | Boundary |
| --- | --- | --- |
| Engineering constitution | `AGENTS.md` | Engineering constraints and guardrails only. |
| Product milestones | `ROADMAP.md` | What to deliver and milestone outcomes only. |
| Execution playbook | `CODEX_PLAN.md` | How to execute and verify delivery only. |
| Phase order | `phases/index.md` | Phase sequence and transition order only. |
| Phase scope and acceptance | `phases/phase-*.md` | Detailed per-phase task scope only. |
| Checkpoint/resume state | `phases/state.md` | Runtime execution pointer/status only. |
| Documentation governance | `docs/01_GOVERNANCE.md` | SSOT boundaries and change rules only. |

Rule: each topic has exactly one owner document. Cross-reference is allowed, rule duplication is not.

## 2. Phase Change Rules

1. Phase content may be added or revised only in `phases/phase-*.md`.
2. Phase ordering may be changed only in `phases/index.md`.
3. Resume/checkpoint values may be changed only in `phases/state.md`.
4. `AGENTS.md`, `ROADMAP.md`, and `CODEX_PLAN.md` must not contain phase task definitions.
5. New phases should keep the two-digit grouping convention (01-12 model) used by `docs/00_INDEX.md`.

## 3. Engineering Rule Change Rules

1. Engineering policy changes must be made in `AGENTS.md`.
2. Every rule change should include a short rationale in the commit/PR description.
3. Changes must preserve explicit architecture constraints unless intentionally superseded.
4. If a change affects verification gates, update `CODEX_PLAN.md` in the same change set.

## 4. Execution Rule Change Rules

1. Execution command/workflow changes must be made in `CODEX_PLAN.md`.
2. `CODEX_PLAN.md` must not define product milestones or phase acceptance requirements.
3. Execution rules must remain container-first unless explicitly re-governed.
4. If execution commands change, verification instructions must be updated consistently.

## 5. Snapshot Requirement After Major Phase

A documentation snapshot is required after each major phase boundary:
- Phase 06 completion (feature tranche complete)
- Phase 09 completion (structure tranche complete)
- Phase 12 completion (production tranche complete)

Required artifacts:
1. Regenerate `docs/gpt_SYSTEM_SNAPSHOT.md` via `gpt/gen_report1.sh`.
2. Regenerate `docs/gpt_ARCHITECTURE_RISK_REPORT.md` via `gpt/gen_report2.sh`.
3. Record completion status in phase reporting and checkpoint state files.
