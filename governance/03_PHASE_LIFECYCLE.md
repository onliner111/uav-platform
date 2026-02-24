# 03_PHASE_LIFECYCLE.md
Phase Lifecycle Specification
阶段生命周期规范

---

# 1. Purpose
# 1. 目的

This document defines how phases are created, executed, completed, and transitioned.

本文件定义阶段如何创建、执行、完成与切换。

It ensures structural discipline across all project phases.

确保所有阶段在结构上保持一致与可控。

---

# 2. Phase Definition
# 2. 阶段定义

Every phase must define:

每个阶段必须定义：

- Objective（目标）
- Scope（范围）
- Constraints（约束）
- Acceptance Criteria（验收标准）
- Exit Criteria（退出条件）

Phase documents must live in:

阶段文件必须放在：

phases/phase-<number><optional-letter>-<name>.md

Example:
phases/phase-07c-tenant-export-purge.md

---

# 3. Phase States
# 3. 阶段状态

Each phase can exist in one of the following states:

每个阶段只能处于以下状态之一：

1. Planned（规划中）
2. Active（执行中）
3. Frozen（冻结）
4. Completed（已完成）
5. Archived（归档）

Execution checkpoint SSOT:

执行检查点单一事实源：

phases/state.md

Mirrored human-readable status:

面向阅读者的同步状态文档：

docs/PROJECT_STATUS.md

---

# 4. Phase Start Rules
# 4. 阶段启动规则

Before activating a phase:

在阶段启动前必须：

- Phase blueprint created.
  阶段蓝图文件已创建。

- Governance alignment verified.
  已验证符合治理规则。

- Scope does not violate architectural invariants.
  范围未违反架构不变量。

---

# 5. Phase Execution Rules
# 5. 阶段执行规则

During execution:

执行期间必须：

- Follow governance constraints.
  遵守治理规则。

- Do not modify completed phase documents.
  不得修改已完成阶段文件。

- Update phases/state.md when execution state changes.
  执行状态变化时更新 phases/state.md。

- Sync docs/PROJECT_STATUS.md after phases/state.md update.
  更新 phases/state.md 后同步 docs/PROJECT_STATUS.md。

- Stay strictly within declared scope.
  严格保持在声明范围内。

---

# 6. Phase Completion Rules
# 6. 阶段完成规则

A phase can be marked Completed only if:

阶段仅在满足以下条件时才可标记为完成：

- All acceptance criteria satisfied.
- Tests validate governance constraints.
- Governance consistency checklist passed.

完成后必须：

- Update phases/state.md
- Sync docs/PROJECT_STATUS.md
- Preserve historical blueprint integrity
- Do NOT alter governance unless intentional

---

# 7. Phase Transition Rules
# 7. 阶段切换规则

To move to next phase:

进入下一阶段必须：

1. Mark current phase Completed.
2. Define next phase blueprint.
3. Update phases/state.md.
4. Sync docs/PROJECT_STATUS.md.
5. Confirm governance compliance.

No implicit phase transitions allowed.
禁止隐式阶段切换。

---

# 8. Governance Supremacy Rule
# 8. 治理优先原则

If a phase document conflicts with governance documents:

若阶段文件与治理文件冲突：

Governance documents take precedence.
以治理文件为准。

---

# End of Document
# 文档结束
