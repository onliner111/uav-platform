# Phase 07C：Tenant 级完整数据导出与清理（Export & Purge Blueprint）
**版本**：V1.0  
**适用仓库**：uav-platform  
**策略前提**：沿用当前 Phase 07A/07B 的 **tenant boundary** 强化方向（广泛使用 `(tenant_id, id)` 唯一约束 + 复合外键 + `ON DELETE RESTRICT`）。  
**目标**：提供 **Tenant 级全量数据导出** 与 **Tenant 级安全清理** 两套能力，并且以“小步可验证、可复跑、可审计”为工程约束。

---

## 0. 关键约束（必须遵守）
1. **租户隔离语义不变**：跨租户访问一律按现有语义返回 `404`（NotFound），权限失败行为保持既有逻辑。
2. **默认不改迁移**：
   - 07C-1/07C-2 **不改 migrations**。
   - 07C-3 若需要新增审计表，可作为独立小步（07C-4）再做。
3. **RESTRICT 导向**：既然 07B 强化外键为 `RESTRICT`，清理必须采用 **依赖顺序删除**（leaf → parent），不得期望数据库 cascade。
4. **工程化输出目录**：所有工程化内容统一放在：
   - `docs/`：面向用户/运维/架构文档
   - `phases/`：阶段蓝图与执行计划
   - `tooling/`：脚本/执行器（跨平台优先 PowerShell + docker compose）
   - `logs/`：运行产物（导出文件、报告、审计日志等）

---

## 1. 07C 的分批路线（强烈推荐按顺序推进）

### 07C-1：Tenant Export Framework（只读导出）
**目标**：先打通导出框架（安全、只读），用于验证 tenant boundary 是否“全表覆盖”。

**交付物（建议）**
- `app/services/tenant_export_service.py`
- `app/api/routers/tenant_export.py`
- `docs/ops/TENANT_EXPORT.md`
- `tests/test_tenant_export.py`
- （可选）`infra/scripts/demo_tenant_export.py` 或 `tooling/tenant_export.ps1`

**导出格式（推荐）**
- JSONL：每表一个文件，适合追加写入与流式处理
- 输出目录：`logs/exports/<tenant_id>/<export_id>/`
  - `manifest.json`（导出摘要：表清单、行数、校验 hash、时间戳、导出版本等）
  - `tables/<table_name>.jsonl`

**导出范围**
- 初期：导出 **所有含 tenant_id 的业务表**（由代码自动发现/或手工清单）
- 若存在不含 tenant_id 的全局表（字典表/系统表）：
  - 仅在 `manifest.json` 标记“全局表”并跳过导出，避免误解

**API（建议）**
- `POST /tenants/{tenant_id}/export`
  - 返回：`{ export_id, status }`
- `GET /tenants/{tenant_id}/export/{export_id}`
  - 返回：状态、表行数、产物路径（本地）
- `GET /tenants/{tenant_id}/export/{export_id}/download`
  - 本地模式：可直接返回 zip（可后续增强）或返回路径信息

**验收（Quality Gate）**
- `ruff`, `mypy`, `pytest`（通过 docker compose）
- 导出产物落在 `logs/exports/...`，并包含 `manifest.json`

---

### 07C-2：Tenant Purge Dry-Run（只统计不删除）
**目标**：输出删除计划（依赖顺序）与每表行数统计，不做任何删除。

**交付物（建议）**
- `app/services/tenant_purge_service.py`（先实现 dry-run）
- `app/api/routers/tenant_purge.py`
- `docs/ops/TENANT_PURGE.md`
- `tests/test_tenant_purge_dry_run.py`

**API（建议）**
- `POST /tenants/{tenant_id}/purge:dry_run`
  - 返回：
    - `plan`: 删除顺序（table list）
    - `counts`: 每表 `row_count`
    - `estimated_rows`: 总行数
    - `safety`: 风险提示（例如：关联过多、耗时预估）

**删除计划生成策略（推荐）**
- **优先：显式清单（可控、可审计）**
  - 在 `phases/phase-07c-tenant-export-purge.md` 中维护“表依赖分层清单”
- **增强：自动拓扑（可选）**
  - 从 SQLAlchemy metadata / 数据库系统表推导外键依赖，得到拓扑排序
  - 输出排序结果并落盘，供人工审核后写回清单（形成闭环）

---

### 07C-3：Tenant Purge Execute（真删，强保护栏）
**目标**：在强保护栏下，按计划删除 tenant 全部数据，并完成删除后验证。

**强保护栏（必须）**
- 先跑 `dry_run` 生成 plan + counts
- 执行 purge 必须提供：
  - `confirm_token`（服务端生成一次性 token）或
  - `confirm_phrase`（例如 `I_UNDERSTAND_THIS_WILL_DELETE_TENANT_DATA`）
- 必须写审计记录（至少落日志；最好后续进表）

**API（建议）**
- `POST /tenants/{tenant_id}/purge`
  - body：`{ confirm_token | confirm_phrase, mode }`
  - mode：`soft`（可选）/ `hard`
- `GET /tenants/{tenant_id}/purge/{purge_id}`
  - 查询进度（若你后续引入 background job）

**删除策略（推荐 Hard Delete）**
- 按依赖顺序：leaf 表 → parent 表
- 每表执行：`DELETE FROM <table> WHERE tenant_id = :tenant_id`
- 每表记录删除行数（用于审计与验证）

**删除后验证（必须）**
- 重新统计所有 tenant-scoped 表：row_count 全部为 0
- 必要时对关键表做一致性验证（例如 users/roles 等）

---

### 07C-4：审计与可观测（推荐单独一步）
**目标**：导出/清理行为可追溯，可用于合规审计与问题回滚定位。

**最小可行**：日志落盘
- `logs/exports/<tenant>/<export_id>/manifest.json`
- `logs/purge/<tenant>/<purge_id>/report.json`

**增强可选**：新增审计表（需 migrations）
- `tenant_export_records`
- `tenant_purge_records`
字段建议：tenant_id, operator, requested_at, started_at, finished_at, status, counts_json, artifact_path, sha256, etc.

---

## 2. 表范围与依赖分层（需要你在推进中逐步完善）
> 说明：07B 正在推进 tenant boundary（批次化），因此 07C 的“完整表清单”要与 `tenant_boundary_matrix.md` 同步更新。  
> 约束：每次新增/强化一批表（07B），应同步更新 07C 的 purge/export 表清单。

**建议做法（强烈推荐）**
- 以 `tenant_boundary_matrix.md` 为唯一真相源（Source of Truth）
- 在 07C 的计划文件里维护：
  - `EXPORT_TABLES`：需要导出的表
  - `PURGE_PLAN_LEVELS`：按层级/依赖排序后的删除计划（level 0 是最 leaf）

示例（伪结构，具体表名以仓库实际为准）：
- Level 0（leaf）：`mission_runs`, `defect_actions`, ...
- Level 1：`missions`, `defects`, `incidents`, `alerts`, ...
- Level 2：`inspection_tasks`, ...
- Level 3（root-ish）：`drones`, `users`, `roles`, `tenants`（注意 tenants 自身是否 tenant-scoped 要谨慎）

> 注意：如果 `tenants` 是全局表（系统租户表），清理 tenant 数据通常 **不删除 tenant 记录本身**，而是把它标记 deleted（可选 soft-delete），避免引用链断裂。

---

## 3. 目录与命名规范（你要求“工程化的东西放一起”）
**建议统一落位**
- `phases/`
  - `phase-07c-tenant-export-purge.md`（本文件：蓝图）
  - `phase-07c-1-export.md`（执行计划）
  - `phase-07c-2-purge-dry-run.md`
  - `phase-07c-3-purge-exec.md`
- `docs/ops/`
  - `TENANT_EXPORT.md`
  - `TENANT_PURGE.md`
- `tooling/`
  - `tenant_export.ps1`
  - `tenant_purge.ps1`
  - `run_quality_gate.ps1`（可复用）

---

## 4. Codex 执行模板（你要求每次都要明确 “Based on …”）

### 4.1 07C-1（导出框架）执行命令模板
```bash
codex -a on-request -s workspace-write "
Based on phases/phase-07c-tenant-export-purge.md and tenant_boundary_matrix.md,
implement Phase 07C-1 Tenant Export framework.

Scope:
- app/services/tenant_export_service.py
- app/api/routers/tenant_export.py
- docs/ops/TENANT_EXPORT.md
- tests/test_tenant_export.py
- optional: tooling/tenant_export.ps1

Rules:
- Tenant-scoped only; cross-tenant returns 404 semantics (preserve existing patterns).
- Export artifacts under logs/exports/<tenant_id>/<export_id>/ including manifest.json.
- Do not modify migrations in this step.
- Run quality gate via docker compose: ruff, mypy, pytest. Report results.

"
```

### 4.2 07C-2（dry-run）执行命令模板
```bash
codex -a on-request -s workspace-write "
Based on phases/phase-07c-tenant-export-purge.md and tenant_boundary_matrix.md,
implement Phase 07C-2 Tenant Purge dry-run (NO DELETION).

Scope:
- app/services/tenant_purge_service.py (dry-run only)
- app/api/routers/tenant_purge.py
- docs/ops/TENANT_PURGE.md
- tests/test_tenant_purge_dry_run.py

Rules:
- Return delete plan (ordered tables) and per-table row counts for the tenant.
- Do not modify migrations.
- Do not delete anything.
- Run quality gate via docker compose: ruff, mypy, pytest. Report results.

"
```

### 4.3 07C-3（真删）执行命令模板
```bash
codex -a on-request -s workspace-write "
Based on phases/phase-07c-tenant-export-purge.md and tenant_boundary_matrix.md,
implement Phase 07C-3 Tenant Purge execute with strong safety rails.

Scope:
- app/services/tenant_purge_service.py (execute)
- app/api/routers/tenant_purge.py
- docs/ops/TENANT_PURGE.md
- tests/test_tenant_purge_execute.py (if needed)

Rules:
- Must require dry_run first; require confirm_token or confirm_phrase.
- Must delete in dependency order (leaf -> parent), tenant_id filtered deletions only.
- Must produce a purge report under logs/purge/<tenant_id>/<purge_id>/report.json.
- Prefer no migrations in this step; if you believe audit tables are required, propose as 07C-4 instead.
- Run quality gate via docker compose: ruff, mypy, pytest, and (if available) e2e. Report results.

"
```

---

## 5. PowerShell 质量门禁（Windows 友好）
> 你之前遇到 “bash / mingw docker 权限不一致”，建议最终把质量门禁脚本落到 `tooling/*.ps1`。

推荐统一命令（你可以在 PowerShell 中执行）：
```powershell
docker compose -f infra/docker-compose.yml run --rm app ruff check app tests infra/scripts
docker compose -f infra/docker-compose.yml run --rm app mypy app
docker compose -f infra/docker-compose.yml run --rm app pytest
```

---

## 6. 风险与注意事项
1. **误删风险**：必须有 confirm_token/phrase + dry-run 前置。
2. **耗时与锁**：大租户清理可能耗时，必要时引入后台 job（可后续 Phase 08/09 做）。
3. **tenant 表本身**：通常不直接 delete tenant 记录；推荐做软删除标记。
4. **表清单同步**：07B 每推进一批表，07C 的 export/purge 计划必须同步更新（以 matrix 为准）。

---

## 7. 验收标准（Definition of Done）
- 07C-1：可对任一 tenant 生成导出产物 + manifest（含表行数/校验信息）
- 07C-2：可输出 dry-run 删除计划与 row counts，不做删除
- 07C-3：在强保护栏下完成硬删除，删除后验证为 0，生成 purge report
- 07C-4（若做）：审计可查、可追溯（日志或表）

---

## 8. 下一步建议（你现在就能做）
1. 先跑 07C-1（导出框架）
2. 把导出结果（manifest）回写/对齐 `tenant_boundary_matrix.md`（确保表覆盖完整）
3. 再推进 07C-2（dry-run），产出可审计的 delete plan
4. 最后 07C-3（真删）

