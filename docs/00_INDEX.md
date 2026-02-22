# 00_INDEX.md - Documentation Index

## 1. Document Hierarchy

1. Governance Layer
- `docs/00_INDEX.md`: documentation navigation and ownership boundaries.
- `docs/01_GOVERNANCE.md`: SSOT and change-control rules.

2. Repository SSOT Layer
- `AGENTS.md`: engineering constitution and hard constraints.
- `ROADMAP.md`: product milestones and capability progression.
- `CODEX_PLAN.md`: execution playbook and delivery workflow.

3. Phase Execution Layer
- `phases/index.md`: canonical phase order.
- `phases/phase-*.md`: per-phase scope and acceptance definitions.
- `phases/state.md`: checkpoint/resume runtime state.
- `phases/reporting.md`: phase reporting contract.

4. Reference and Manual Layer
- `docs/Architecture_Overview_*.md`
- `docs/Deployment_Guide_*.md`
- `docs/Admin_Manual_*.md`
- `docs/User_Manual_*.md`
- `docs/API_Appendix_*.md`

5. Generated Report Layer
- Auto-generated system snapshots and risk reports (see section 4).

## 2. SSOT Mapping

| Domain | Single Source of Truth | Notes |
| --- | --- | --- |
| Engineering rules | `AGENTS.md` | Global engineering constraints only. |
| Product milestones | `ROADMAP.md` | Outcome and milestone planning only. |
| Execution workflow | `CODEX_PLAN.md` | How to execute, validate, and deliver. |
| Phase sequence | `phases/index.md` | Canonical execution order. |
| Phase definition | `phases/phase-*.md` | Scope and acceptance per phase. |
| Resume state | `phases/state.md` | Current phase pointer and execution status. |
| Governance policy | `docs/01_GOVERNANCE.md` | Change-control and SSOT boundaries. |

Conflict handling rule: if two documents disagree, follow the domain owner above instead of duplicating rules.

## 3. Phase Grouping Model

- Group A (Feature Delivery): phases 01-06.
- Group B (Structure Hardening): phases 07-09.
- Group C (Production Readiness): phases 10-12.

Current repository contains phase files for 01-06. Group B and Group C are reserved for future phase documents and should keep this numbering model.

## 4. Auto-Generated Reports Reference

- `docs/gpt_SYSTEM_SNAPSHOT.md`
  - Source script: `gpt/gen_report1.sh`
  - Purpose: full repository/system snapshot.
- `docs/gpt_ARCHITECTURE_RISK_REPORT.md`
  - Source script: `gpt/gen_report2.sh`
  - Purpose: architecture and engineering risk scan.
- `docs/SYSTEM_SNAPSHOT.md`
  - Legacy/baseline snapshot reference.

Generated reports are evidence artifacts, not rule-defining SSOT documents.
