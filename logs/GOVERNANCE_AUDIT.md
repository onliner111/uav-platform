# Governance Consistency Audit

- Audit target: `governance/05_GOVERNANCE_CONSISTENCY_CHECKLIST.md`
- Audit mode: full repository consistency audit (read-only analysis; no source changes)
- Audit date: 2026-02-24
- Overall result: **FAIL**

## Section Status Summary

| Checklist Section | Status |
|---|---|
| 1. Purpose | PASS |
| 2. Governance Layer Consistency | FAIL |
| 3. Phase Alignment | FAIL |
| 4. Application & Infrastructure Integrity | FAIL |
| 5. Documentation Accuracy | FAIL |
| 6. Automation & Execution Integrity | FAIL |
| 7. Layering Integrity Model | FAIL |
| 8. Final Release Gate | FAIL |

## 1) Purpose - PASS

Evidence:
- Checklist purpose and trigger conditions are explicit.
- File refs:
  - `governance/05_GOVERNANCE_CONSISTENCY_CHECKLIST.md:7`
  - `governance/05_GOVERNANCE_CONSISTENCY_CHECKLIST.md:19`
  - `governance/05_GOVERNANCE_CONSISTENCY_CHECKLIST.md:22`

Grep evidence:
```text
rg -n "# 1\. Purpose|Before starting a new major phase|After completing a phase|Before architectural refactoring|Before production release" governance/05_GOVERNANCE_CONSISTENCY_CHECKLIST.md
7:# 1. Purpose
19:- Before starting a new major phase
20:- After completing a phase
21:- Before architectural refactoring
22:- Before production release
```

## 2) Governance Layer Consistency - FAIL

### Item checks
- `governance/01_GOVERNANCE.md` reflects invariants: **PASS**
- `governance/02_REPO_LAYOUT.md` matches actual repo: **FAIL**
- `governance/03_PHASE_LIFECYCLE.md` aligns with workflow: **FAIL**
- `governance/04_CHAT_INTERACTION_PROTOCOL.md` enforced in new chats: **FAIL**
- `governance/ROADMAP.md` matches real milestone progression: **FAIL**
- `governance/tenant_boundary_matrix.md` up-to-date: **FAIL**

Key evidence:
- Invariants are present in governance:
  - `governance/01_GOVERNANCE.md:29`, `:32`, `:38`
- Repo layout mismatch:
  - Requires docs artifacts: `governance/02_REPO_LAYOUT.md:108`, `:109`
  - Missing files: `docs/PROJECT_STATUS.md` and `docs/CHAT_BOOTSTRAP.md`
  - Layout says all automation in `tooling/`: `governance/02_REPO_LAYOUT.md:148`, `:149`
  - But automation exists in `infra/scripts/*`
- Phase lifecycle/workflow mismatch:
  - Lifecycle requires `docs/PROJECT_STATUS.md`: `governance/03_PHASE_LIFECYCLE.md:61`
  - Actual executor uses `phases/state.md`: `infra/scripts/run_all_phases.sh:4`, `:120`
- Chat protocol and Based-on enforcement gap:
  - Requirement: `governance/04_CHAT_INTERACTION_PROTOCOL.md:59`
  - Missing in recent instruction files: `phases/index.md`, `phases/resume.md`, `governance/AGENTS.md`, `infra/scripts/run_all_phases.sh`
- Roadmap/progression mismatch:
  - Roadmap milestone scope is 6 stages: `governance/ROADMAP.md:55`, `:64`, `:126`
  - Progress includes phase-07a completion: `logs/PROGRESS.md:13`, `:14`
- Tenant matrix stale claims:
  - Matrix says `session.get` still used for Alert/Command/Incident: `governance/tenant_boundary_matrix.md:22`, `:23`, `:24`
  - Current services use tenant-scoped queries/helpers:
    - `app/services/alert_service.py:206`, `:221`, `:265`
    - `app/services/command_service.py:76`, `:92`, `:110`
    - `app/services/incident_service.py:45`, `:71`, `:82`

Grep evidence:
```text
Test-Path docs/PROJECT_STATUS.md -> False
MISSING: docs/CHAT_BOOTSTRAP.md

rg -n "STATE_FILE|Resume execution from phases/state.md" infra/scripts/run_all_phases.sh
4:STATE_FILE="phases/state.md"
120:Resume execution from phases/state.md current_phase and execute remaining phases sequentially in autonomous mode

rg -n "Based on" phases/index.md phases/resume.md infra/scripts/run_all_phases.sh governance/AGENTS.md logs/PROGRESS.md
NO_MATCH: Based on not found in listed recent instruction files
```

## 3) Phase Alignment - FAIL

### Item checks
- `docs/PROJECT_STATUS.md` reflects active phase: **FAIL**
- `phases/state.md` indicates correct execution state: **FAIL**
- Completed phases preserved/immutable: **PASS**
- Current phase scope within blueprint definition: **FAIL**

Key evidence:
- Missing required status file:
  - `docs/PROJECT_STATUS.md` not present
- State/progress divergence:
  - State says done at phase-06: `phases/state.md:3`, `:4`, `:8`
  - Progress marks phase-07a completed: `logs/PROGRESS.md:13`, `:14`
- Completed phase immutability appears preserved:
  - `git log -- phases/phase-01-inspection.md ... phase-06-reporting.md` shows only initial add commit `1900ea2`
- Scope and sequence divergence:
  - Phase index defines only 1-6: `phases/index.md:11`-`:16`
  - Phase-07 blueprints exist and are being executed: `phases/phase-07-master-blueprint.md`, `logs/PROGRESS.md:13`, `:14`

Grep evidence:
```text
rg -n "phase-07|phase-06|DONE|last_success_phase|updated_at" phases/state.md logs/PROGRESS.md
phases/state.md:3:- current_phase: DONE
phases/state.md:4:- last_success_phase: phase-06-reporting.md
phases/state.md:8:- updated_at: 2026-02-21T02:30:00Z
logs/PROGRESS.md:13:- [x] phase-07a-identity-preview.md - ✅ success ...
logs/PROGRESS.md:14:- [x] phase-07a-core-batch-a.md - ✅ success ...
```

## 4) Application & Infrastructure Integrity - FAIL

### Item checks
- Tenant isolation enforced: **PASS (partial coverage in code/tests)**
- Composite foreign keys preserved: **FAIL**
- Migrations follow expand -> backfill -> enforce: **PASS (phase07 batches present)**
- Tests validate governance constraints: **PASS**
- No cross-tenant leakage possible: **FAIL**

Key evidence:
- Tenant-scoped service lookups exist broadly:
  - `app/services/mission_service.py:47`
  - `app/services/inspection_service.py:53`
  - `app/services/defect_service.py:73`
- Composite FK gaps remain in tenant-owned relationships:
  - `DroneCredential.drone_id` single-column FK: `app/domain/models.py:159`
  - `CommandRequestRecord.drone_id` single-column FK: `app/domain/models.py:309`
  - Migration-level single-column constraints:
    - `infra/migrations/versions/202602190003_registry_phase2.py:46`
    - `infra/migrations/versions/202602190005_command_phase5.py:38`
- Expand/backfill/enforce pattern is present for phase07a and phase07b b1-b3:
  - `202602220008/009/010`, `202602220011/012/013`, `202602230014/015/016`, `202602230017/018/019`, `202602230020/021/022`
- Governance tests exist for isolation/composite constraints:
  - `tests/test_identity.py:70`, `:178`
  - `tests/test_mission.py:225`, `:315`
  - `tests/test_inspection.py:85`
  - `tests/test_defect.py:126`
  - `tests/test_incident.py:31`
- Leak-risk still unresolved in boundary matrix (PARTIAL/HIGH domains):
  - `governance/tenant_boundary_matrix.md:22`, `:24`, `:26`

Grep evidence:
```text
rg -n "ForeignKeyConstraint" infra/migrations/versions/202602190003_registry_phase2.py
46:        sa.ForeignKeyConstraint(["drone_id"], ["drones.id"], ondelete="CASCADE"),

rg -n "ForeignKeyConstraint" infra/migrations/versions/202602190005_command_phase5.py
38:        sa.ForeignKeyConstraint(["drone_id"], ["drones.id"], ondelete="CASCADE"),

rg --files infra/migrations/versions | rg "phase07a_.*(expand|backfill|enforce)|phase07b_b[1-3]_.*(expand|backfill|enforce)"
... 15 files matched ...
```

## 5) Documentation Accuracy - FAIL

### Item checks
- User manuals reflect actual API behavior: **FAIL**
- Deployment guides match real infra setup: **PASS**
- Deprecated documents clearly marked: **FAIL**
- No document contradicts governance layer: **FAIL**

Key evidence:
- API behavior gap for tenant export:
  - Implemented endpoints: `app/api/routers/tenant_export.py:49`, `:70`, `:89`
  - Documented in ops doc: `docs/ops/TENANT_EXPORT.md:14`, `:17`, `:20`
  - Not present in API appendix/user manual v2 (`NO_MATCH` on tenant export patterns)
- Deployment guide points to existing compose file:
  - `docs/Deployment_Guide_V2.0.md:42`, `:83`
  - `infra/docker-compose.yml` exists
- No deprecation markers found across docs:
  - `NO_MATCH: deprecated|废弃|过时...`
- Snapshot docs contradict current repo migration state:
  - Snapshot says head `202602210007`: `docs/SYSTEM_SNAPSHOT.md:390`
  - Repo contains later migrations `202602230020/021/022`

Grep evidence:
```text
rg -n -F "/tenants/{tenant_id}/export" app/api/routers/tenant_export.py docs/API_Appendix_V2.0.md docs/User_Manual_V2.0.md docs/ops/TENANT_EXPORT.md
app/api/routers/tenant_export.py:49:    "/tenants/{tenant_id}/export",
docs/ops/TENANT_EXPORT.md:14:- `POST /api/tenants/{tenant_id}/export?...`

rg -n "/api/tenants/\{|tenant export|tenant-export|租户导出" docs/API_Appendix_V2.0.md docs/User_Manual_V2.0.md
NO_MATCH: tenant export endpoints not documented in API/User manual v2

rg -n "deprecated|废弃|过时|不再维护|superseded" docs
NO_MATCH: no deprecation markers found in docs/
```

## 6) Automation & Execution Integrity - FAIL

### Item checks
- `EXECUTION_PLAYBOOK.md` defines workflow only: **PASS**
- Milestones defined only in `governance/ROADMAP.md` and `phases/`: **FAIL**
- Codex executions reference specific phase documents: **PASS**
- All execution instructions include `Based on`: **FAIL**

Key evidence:
- Playbook scope-only clauses:
  - `governance/EXECUTION_PLAYBOOK.md:8`, `:14`, `:36`
- Milestone definition drift outside authoritative files:
  - Milestone progression language appears in snapshot docs: `docs/SYSTEM_SNAPSHOT.md:426`
  - Execution script also emits milestone tags: `infra/scripts/run_all_phases.sh:71`, `:148`
- Codex execution logs reference phase files:
  - `logs/phase-01-inspection.md.report.md:1` ... through `logs/phase-06-reporting.md.report.md:1`
- Based-on missing in recent instruction files:
  - Recent change set includes `phases/index.md`, `phases/resume.md`, `infra/scripts/run_all_phases.sh` (commit `a3dff92`)
  - `rg -n "Based on"` returns no matches for those files

Grep evidence:
```text
git log --name-only --pretty=format:"COMMIT %H %ad %s" --date=iso -n 1
COMMIT a3dff92... Refactor repo structure: governance + tooling consolidation
... phases/index.md
... phases/resume.md
... infra/scripts/run_all_phases.sh

rg -n "Based on" phases/index.md phases/resume.md infra/scripts/run_all_phases.sh governance/AGENTS.md logs/PROGRESS.md
NO_MATCH: Based on not found in listed recent instruction files
```

## 7) Layering Integrity Model - FAIL

Result: **FAIL** (cross-layer behavior contradicts declared governance authority chain)

Evidence:
- Governance workflow says phase state comes from `docs/PROJECT_STATUS.md`:
  - `governance/EXECUTION_PLAYBOOK.md:62`
  - `governance/03_PHASE_LIFECYCLE.md:61`, `:96`, `:132`
- Execution layer effectively overrides with `phases/state.md`:
  - `infra/scripts/run_all_phases.sh:4`, `:120`
  - `phases/resume.md:15`, `:16`
  - `governance/AGENTS.md:170`, `:172`
- Required governance-referenced artifact is missing:
  - `docs/PROJECT_STATUS.md` absent

## 8) Final Release Gate - FAIL

Release gate status: **BLOCKED**

Reasons:
- Not all above checks pass (sections 2-7 fail)
- `PROJECT_STATUS.md` not updated (file missing)
- Governance violations detected (milestone drift, layer override, Based-on gaps)
- Tenant boundary gaps unresolved (multiple PARTIAL/HIGH domains)

Evidence refs:
- `governance/05_GOVERNANCE_CONSISTENCY_CHECKLIST.md:117`-`:121`
- `governance/tenant_boundary_matrix.md:22`, `:24`, `:26`

---

## Required Detection Results

### A) Duplicate milestone definitions - DETECTED (FAIL)

Evidence:
- Canonical roadmap milestone framing (M0/M1 and 6 phases): `governance/ROADMAP.md:49`, `:55`, `:64`-`:126`
- Separate execution sequence definition (only phase 1-6): `phases/index.md:11`-`:16`
- Additional completed milestones outside that sequence: `logs/PROGRESS.md:13`, `:14` (phase-07a)

### B) Cross-layer override violations - DETECTED (FAIL)

Evidence:
- Governance requires `docs/PROJECT_STATUS.md` as active-phase reference.
- Execution infra/phase tooling uses `phases/state.md` as operative SSOT.

Refs:
- `governance/EXECUTION_PLAYBOOK.md:62`
- `governance/03_PHASE_LIFECYCLE.md:61`
- `infra/scripts/run_all_phases.sh:4`, `:120`
- `phases/resume.md:15`

### C) Missing `Based on` usage in recent changes - DETECTED (FAIL)

Evidence:
- Recent changed instruction files from latest commit include execution docs/scripts (`phases/index.md`, `phases/resume.md`, `infra/scripts/run_all_phases.sh`).
- No `Based on` marker found in those files.

Refs:
- Commit: `a3dff92`
- `NO_MATCH: Based on not found in listed recent instruction files`

### D) Tenant boundary violations - DETECTED (FAIL)

Evidence:
- Single-column FK links in tenant-owned relationships (risk of tenant mismatch at DB level):
  - `app/domain/models.py:159` (`DroneCredential.drone_id`)
  - `app/domain/models.py:309` (`CommandRequestRecord.drone_id`)
  - `infra/migrations/versions/202602190003_registry_phase2.py:46`
  - `infra/migrations/versions/202602190005_command_phase5.py:38`
- Boundary matrix still shows unresolved PARTIAL/HIGH domains:
  - `governance/tenant_boundary_matrix.md:22`, `:24`, `:26`

---

## Conclusion

Governance consistency is currently **not release-ready**. Primary blockers are governance-workflow source drift (`PROJECT_STATUS` vs `phases/state`), milestone-definition inconsistency, missing `Based on` in recent execution instructions, and unresolved tenant-boundary DB constraints.
