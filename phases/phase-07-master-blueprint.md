# Phase 07 Master Blueprint

## 0. Header
- **Title:** Phase 07 Master Blueprint
- **Purpose:** Upgrade from logical multi-tenant to enforced multi-tenant boundaries (DB + lookup + RBAC + audit).
- **Scope:** `app/`, `infra/migrations`, `tests`, `governance`, `tooling`, `docs`.
- **Non-goals:** Do not involve LLM in real-time control loops; focus on tasking/supervision/commands only.

## 1. Naming & File Conventions
- Phase files live under `phases/`.
- Governance documents live under `governance/`.
- User/deploy docs live under `docs/`.
- Automation scripts live under `tooling/`.
- Logs and progress records live under `logs/`.
- Phase naming uses kebab-case:
  - `phase-07a-...`
  - `phase-07b-...`
  - `phase-07c-...`
  - `phase-07d-...`
  - `phase-07e-...`
- Batch naming:
  - `07A Batch A/B/C...`
  - Lookup batches: `C1/C2/C3/C4`
- Current-state references:
  - Canonical phase checkpoint: `phases/state.md`
  - Execution log/progress: `logs/PROGRESS.md` (if present and active)
  - Update both when status changes.

## 2. Phase 07 Overview (Executive Summary)
### What success looks like
- Tenant boundaries are enforced at three layers:
  - DB constraints reject cross-tenant references.
  - Service lookups are tenant-scoped (no id-only tenant-owned fetches).
  - RBAC and audit provide policy enforcement and traceability.
- Cross-tenant access returns `404` semantics on protected resources.
- Regression suite stays green (`ruff`, `mypy`, `pytest`, e2e, Alembic upgrade).

### Why DB constraints are insufficient without lookup hardening
- DB constraints prevent illegal writes, but id-only reads can still resolve cross-tenant rows before post-check.
- Lookup hardening moves tenant checks into query paths, reducing accidental leaks and inconsistent error behavior.

### Why lookup hardening is insufficient without RBAC and audit
- Tenant scoping alone does not enforce role permissions for allowed in-tenant actions.
- Without audit, privileged actions are not reviewable for compliance and incident response.

### How changes stay small and reversible
- Use 3-step migration policy for schema changes:
  - Expand
  - Backfill + validate
  - Enforce
- Deliver in small, isolated batches (`A`, `B1`, `B2`, `C`, `C1`...`C4`).
- One batch per commit; rollback by reverting the batch commit when feasible.

## 3. 07A Tenant Boundary Hardening (DB + Lookup)

### 07A-1 Identity Boundary
- **Status:** DONE
- **Goal:** Enforce tenant-safe user-role bindings at DB and service layers.
- **Tables/models affected:** `users`, `roles`, `user_roles`, `User`, `Role`, `UserRole`.
- **Services/routes affected:** `app/services/identity_service.py` user/role bind-unbind and permission collection paths.
- **Migration policy (schema change):**
  - Expand: add `user_roles.tenant_id`, parent `UNIQUE (tenant_id, id)`.
  - Backfill + validate: fill `tenant_id`; fail on tenant mismatch.
  - Enforce: composite PK/FKs; drop legacy tenant-unsafe FKs.
- **Lookup policy:** No `session.get` for tenant-scoped models; use tenant-scoped helper/query.
- **Tests to add/adjust:**
  - Cross-tenant bind/unbind returns `404`.
  - Permission collection remains tenant-scoped.
  - DB rejects cross-tenant `user_roles` links.
- **Verification checklist:**
  - [ ] `ruff check .`
  - [ ] `mypy app`
  - [ ] `pytest`
  - [ ] `alembic upgrade head`
  - [ ] Cross-tenant bind/unbind verified as `404`
- **Rollback strategy:** Drop composite FKs/PK, restore legacy keys/FKs in reverse order, retain data integrity checks.
- **Definition of Done (DoD):**
  - [ ] Composite identity constraints active
  - [ ] Identity lookups tenant-scoped
  - [ ] Tests covering boundary behavior merged

### 07A-2 Core Batch A
- **Status:** DONE
- **Goal:** Enforce tenant-safe links for mission graph entry points.
- **Tables/models affected:** `drones`, `missions`, `mission_runs`, `Drone`, `Mission`, `MissionRun`.
- **Services/routes affected:** `registry_service`, `mission_service`; mission CRUD/state/approval and drone resolution paths.
- **Migration policy (schema change):**
  - Expand: parent unique keys and tenant-prefixed indexes.
  - Backfill + validate: verify `missions.drone_id` and `mission_runs.mission_id` tenant match.
  - Enforce: add composite FKs, remove replaced single-column FKs.
- **Lookup policy:** No id-only fetch for tenant-owned mission/drone records.
- **Tests to add/adjust:**
  - Cross-tenant drone/mission resource access returns `404`.
  - Cross-tenant mission references rejected.
  - Same-tenant flows remain green.
- **Verification checklist:**
  - [ ] `ruff check .`
  - [ ] `mypy app`
  - [ ] `pytest`
  - [ ] e2e smoke for mission/drone flows
  - [ ] DB negative tests for composite FKs
- **Rollback strategy:** Revert batch commit and/or migration downgrade in reverse constraint order.
- **Definition of Done (DoD):**
  - [ ] Composite mission/drone constraints active
  - [ ] Mission/drone lookup hardening complete
  - [ ] Regression coverage merged

### 07A-3 Core Batch B
- **Status:** PLANNED
- **Plan split:** `B1 templates+tasks`, `B2 observations`

#### 07A-3 B1 Templates + Tasks
- **Goal:** Enforce tenant-safe links across `inspection_templates` and `inspection_tasks`.
- **Tables/models affected:** `inspection_templates`, `inspection_tasks`, `InspectionTemplate`, `InspectionTask`.
- **Services/routes affected:** `inspection_service` template/task CRUD and listing paths.
- **Migration policy (schema change):**
  - Expand: add parent uniqueness/indexes.
  - Backfill + validate: verify task `template_id`/`mission_id` tenant match.
  - Enforce: composite FK conversion for template/task references.
- **Lookup policy:** Use tenant-scoped helper for template/task get-by-id.
- **Tests to add/adjust:** Cross-tenant template/task linkage rejected; `404` on cross-tenant task/template IDs.
- **Verification checklist:**
  - [ ] DB cross-tenant insert/update fails
  - [ ] API/service `404` semantics preserved
  - [ ] In-tenant template/task workflows pass
- **Rollback strategy:** Downgrade migration for B1; revert B1 commit independently.
- **Definition of Done (DoD):**
  - [ ] Template/task composite constraints enabled
  - [ ] Tenant-scoped lookup enforcement complete
  - [ ] Tests updated and green

#### 07A-3 B2 Observations
- **Goal:** Enforce tenant-safe links for `inspection_observations`.
- **Tables/models affected:** `inspection_observations`, `InspectionObservation` (+ parent refs to tasks/drones).
- **Services/routes affected:** `inspection_service` observation create/read/update flows.
- **Migration policy (schema change):**
  - Expand: required indexes.
  - Backfill + validate: verify `task_id`/`drone_id` tenant match when non-null.
  - Enforce: composite FK conversion to task/drone parents.
- **Lookup policy:** Observation lookups must include tenant filter.
- **Tests to add/adjust:** Cross-tenant task/drone observation references fail; observation read/write cross-tenant returns `404`.
- **Verification checklist:**
  - [ ] Composite FKs verified in schema
  - [ ] Negative tenant mismatch tests pass
  - [ ] Existing observation workflows unaffected
- **Rollback strategy:** Isolated B2 rollback path; remove enforced constraints in reverse order.
- **Definition of Done (DoD):**
  - [ ] Observation constraints enforced
  - [ ] Lookup hardening complete
  - [ ] Test and migration checks pass

### 07A-4 Core Batch C (Defects Domain DB Constraints)
- **Status:** PLANNED
- **Goal:** Enforce tenant-safe defect lineage in DB.
- **Tables/models affected:** `defects`, `defect_actions`, `Defect`, `DefectAction`.
- **Services/routes affected:** `defect_service` create/update/status/action paths.
- **Migration policy (schema change):**
  - Expand: unique/index prerequisites.
  - Backfill + validate: verify `defects.observation_id` and `defect_actions.defect_id` tenant consistency.
  - Enforce: composite FK conversion and strict tenant integrity.
- **Lookup policy:** No id-only defect/defect-action fetches.
- **Tests to add/adjust:** Cross-tenant defect lineage rejected at DB and service layers; `404` semantics for cross-tenant IDs.
- **Verification checklist:**
  - [ ] DB composite FKs enforced
  - [ ] Service validation prevents cross-tenant references
  - [ ] Defect lifecycle regression tests green
- **Rollback strategy:** Reverse migration and isolate rollback to Batch C commit.
- **Definition of Done (DoD):**
  - [ ] Defect domain constraints active
  - [ ] Service checks aligned with DB rules
  - [ ] Tests and quality gate green

### 07A-5 Lookup Hardening

#### 07A-5 C1 inspection_service + defect_service
- **Status:** DONE
- **Note:** `pytest` passed for delivered C1 changes.
- **Goal:** Remove tenant-scoped id-only lookups in inspection/defect services.
- **Tables/models affected:** `InspectionTemplate`, `InspectionTask`, `InspectionExport`, `InspectionObservation`, `Defect`.
- **Services/routes affected:** `app/services/inspection_service.py`, `app/services/defect_service.py`.
- **Migration policy:** Not applicable (lookup hardening only, no schema changes).
- **Lookup policy:** Replace `session.get(Model, id)` with tenant-scoped helper/query.
- **Tests to add/adjust:** Existing inspection/defect tests for cross-tenant `404` and in-tenant pass paths.
- **Verification checklist:**
  - [ ] `rg -n "session\\.get\\(" app/services` reviewed for scoped models
  - [ ] `pytest` passing
  - [ ] Cross-tenant behavior preserved as `404`
- **Rollback strategy:** Revert C1 commit only; no DB rollback required.
- **Definition of Done (DoD):**
  - [ ] No tenant-scoped id-only lookup remains in C1 services
  - [ ] Tests green
  - [ ] Error/status behavior parity preserved

#### 07A-5 C2 incident_service + alert_service
- **Status:** NEXT
- **Goal:** Remove tenant-scoped id-only lookups in incident/alert services.
- **Tables/models affected:** `Incident`, `AlertRecord`.
- **Services/routes affected:** `app/services/incident_service.py`, `app/services/alert_service.py`.
- **Migration policy:** Not applicable (lookup hardening only).
- **Lookup policy:** Tenant-scoped helper/query required for incident/alert get-by-id paths.
- **Tests to add/adjust:** Incident task creation and alert lifecycle cross-tenant `404` tests.
- **Verification checklist:**
  - [ ] `session.get` removed/replaced for tenant-owned lookups
  - [ ] Incident/alert tests pass
  - [ ] e2e spot-check of alert lifecycle
- **Rollback strategy:** Revert C2 commit only.
- **Definition of Done (DoD):**
  - [ ] C2 lookups hardened
  - [ ] Tests and semantics verified

#### 07A-5 C3 command_service
- **Status:** PLANNED
- **Goal:** Tenant-scope command/drone lookup paths used by command flows.
- **Tables/models affected:** `CommandRequestRecord`, `Drone`.
- **Services/routes affected:** `app/services/command_service.py`.
- **Migration policy:** Not applicable (lookup hardening only).
- **Lookup policy:** Command and drone resolution must include tenant filter in query path.
- **Tests to add/adjust:** Command dispatch/query/ack paths keep in-tenant success and cross-tenant `404`.
- **Verification checklist:**
  - [ ] No tenant-owned id-only `session.get` in command service
  - [ ] Command tests green
  - [ ] No regression in command state transitions
- **Rollback strategy:** Revert C3 commit only.
- **Definition of Done (DoD):**
  - [ ] Command lookups hardened
  - [ ] Regression coverage complete

#### 07A-5 C4 identity_service tenant-scoped lookups
- **Status:** PLANNED
- **Goal:** Hard-scope identity user/role lookups (tenant-owned entities only).
- **Tables/models affected:** `User`, `Role` (global tables like `Tenant`, `Permission` remain global logic).
- **Services/routes affected:** `app/services/identity_service.py`.
- **Migration policy:** Not applicable for lookup-only C4 tasks.
- **Lookup policy:** `User`/`Role` id lookups require tenant predicate; global models follow global lookup rules.
- **Tests to add/adjust:** User/role CRUD and bind/unbind retain `404` cross-tenant behavior.
- **Verification checklist:**
  - [ ] Tenant-scoped helper methods in identity service
  - [ ] User/role tests pass with `404` cross-tenant
  - [ ] Global model lookups unchanged where intended
- **Rollback strategy:** Revert C4 commit only.
- **Definition of Done (DoD):**
  - [ ] User/role lookup hardening complete
  - [ ] Identity tests green

## 4. 07B RBAC Boundary
- **Deliverables:**
  - `governance/rbac_matrix.md`
  - Policy rule definitions (permission-to-action mapping)
  - Route guards integrated into API layer
- **Implementation strategy:**
  - Centralize authorization entrypoint via `authorize(...)`.
  - Make services/routes call one consistent policy path.
  - Preserve `404` semantics for cross-tenant resource requests even when permission is absent.
- **Tests:**
  - Missing permission returns `403`.
  - Cross-tenant access remains `404` (not `403`).
  - In-tenant allowed actions remain successful.
- **Definition of Done (DoD):**
  - [ ] RBAC matrix documented and approved
  - [ ] Central authorization path wired for protected routes
  - [ ] `403` vs `404` behavior tested and stable

## 5. 07C Audit & Traceability
- **Deliverables:**
  - `docs/Audit_Log_Spec_V1.0.md`
  - `audit_events` model/table (or equivalent event sink abstraction)
  - Audit API for retrieval/filter/export
- **Events to log:**
  - `create`
  - `update`
  - `delete`
  - `export`
  - `command`
  - `approval`
- **Tests:**
  - Write operations emit audit events with tenant/user/action metadata.
  - Event query API enforces tenant visibility.
- **Definition of Done (DoD):**
  - [ ] Audit spec published
  - [ ] Audit storage path implemented
  - [ ] Write-path event emission covered by tests

## 6. 07D Data Integrity & Backfill Safety
- **Deliverables:**
  - Integrity scan script in `tooling/` (example target: `tooling/tenant_integrity_scan.py`).
  - Checks:
    - `tenant_id` nulls
    - tenant FK mismatches
    - orphaned child rows
- **How to run:**
  - Run pre-enforce and post-enforce in migration workflow.
  - Save outputs under `logs/` (example: `logs/phase-07-integrity-scan-YYYYMMDD-HHMMSS.log`).
- **CI smoke target:**
  - Add lightweight integrity scan to CI for migration smoke environments.
- **Definition of Done (DoD):**
  - [ ] Integrity script exists and is documented
  - [ ] Log outputs written to `logs/`
  - [ ] CI smoke target executes and fails on integrity issues

## 7. 07E Packaging & Governance
- **Deliverables:**
  - `governance/tenant_boundary_rules.md`
  - `governance/migration_rules.md`
  - `governance/service_lookup_rules.md`
- **Tooling:**
  - Add/standardize `tooling/codex/run.ps1` modes:
    - `doc`
    - `build`
    - `db`
  - Recommended flags:
    - `-Mode doc -Strict`
    - `-Mode build -Lint -Typecheck -Test`
    - `-Mode db -UpgradeHead -IntegrityScan`
- **PR checklist additions:**
  - Tenant-boundary impact declared (`yes/no`).
  - Migration type declared (`expand/backfill/enforce`).
  - `session.get` grep reviewed for touched services.
  - `403/404` semantics tested where applicable.
  - Audit event impact documented.
- **Definition of Done (DoD):**
  - [ ] Governance docs published
  - [ ] Tooling modes available and documented
  - [ ] PR template/checklist updated

## 8. Execution Orchestration
- Recommended order:
  - Finish all `07A` work before starting `07B` or `07C`.
- Required batch sequencing:
  - Lookup hardening: `C1 -> C2 -> C3 -> C4`
  - Inspection chain: `B1 -> B2`
- Quality gate for each batch:
  - `ruff`
  - `mypy`
  - `pytest`
  - e2e smoke
  - `alembic upgrade head`
- Grep checks:
  - `rg -n "session\\.get\\(" app/services`
  - Confirm remaining hits are global/non-tenant/composite-safe patterns only.
- Commit strategy:
  - One batch per commit.
  - Optional lightweight tags (example: `phase-07a-c2-done`).
  - Keep rollback path isolated by batch.

## 9. Current Status
- **DONE**
  - `07A-1 Identity boundary`
  - `07A-2 Core Batch A`
  - `07A-5 C1 inspection_service + defect_service` (`pytest` passed)
- **NEXT**
  - `07A-5 C2 incident_service + alert_service`
  - Then `07A-3 B1 templates+tasks`
  - Then `07A-3 B2 observations`

### Recommended Next 3 Actions
1. Execute `07A-5 C2` lookup hardening with isolated commit and targeted incident/alert regression tests.
2. Deliver `07A-3 B1` schema migration (expand/backfill+validate/enforce) and inspection template/task service updates.
3. Deliver `07A-3 B2` observation constraints and tests, then re-run full quality gate before moving to `07A-4`.
