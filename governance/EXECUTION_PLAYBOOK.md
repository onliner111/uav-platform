# EXECUTION_PLAYBOOK.md
Execution Workflow Reference
执行流程参考

---

# IMPORTANT NOTICE
# 重要声明

This document defines execution workflow only.

本文件仅定义执行流程。

Milestones, phase boundaries, and product roadmap are defined exclusively in:

里程碑、阶段边界与产品路线图仅由以下文件定义：

- governance/ROADMAP.md
- phases/phase-*.md

This file is NOT the Single Source of Truth (SSOT) for milestones.

本文件不是里程碑或阶段定义的单一事实来源（SSOT）。

If any conflict exists between this document and governance/ROADMAP.md,
ROADMAP.md takes precedence.

若本文件与 governance/ROADMAP.md 冲突，以 ROADMAP.md 为准。

---

# 1. Purpose
# 1. 目的

This document standardizes how work is executed,
not what milestones are defined.

本文件规范“如何执行”，
而非“定义做什么”。

---

# 2. Execution Principles
# 2. 执行原则

- All implementation must reference a phase blueprint.
  所有实现必须引用阶段蓝图。

- Execution checkpoint SSOT is `phases/state.md`.
  执行检查点单一事实源为 `phases/state.md`。

- `docs/PROJECT_STATUS.md` is a mirrored status view, not execution SSOT.
  `docs/PROJECT_STATUS.md` 是同步状态视图，不是执行 SSOT。

- All execution instructions must include:
  所有执行指令必须包含：

  Based on: <specific file path>

- No execution may redefine governance rules.
  执行不得修改治理规则。

---

# 3. Deterministic Workflow
# 3. 确定性执行流程

1. Confirm active phase from phases/state.md.
2. Load corresponding phase blueprint.
3. Execute strictly within scope.
4. Validate using tests.
5. Update phases/state.md if execution state changes.
6. Sync docs/PROJECT_STATUS.md after phases/state.md update.

---

# 4. Non-Authority Clause
# 4. 非权威条款

This document provides workflow reference only.

本文件仅为流程参考。

It does not:

- Define product scope
- Define phase boundaries
- Override governance layer

不定义产品范围；
不定义阶段边界；
不覆盖治理层。

---

# End of Document
# 文档结束
