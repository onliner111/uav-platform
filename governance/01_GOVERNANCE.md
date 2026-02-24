# 01_GOVERNANCE.md
Architecture Invariants & SSOT Definition
架构不变量与单一事实来源定义

---

# 1. Purpose
# 1. 目的

This document defines architectural invariants and the Single Source of Truth (SSOT) rules of this repository.

本文件定义仓库的架构不变量与单一事实来源（SSOT）规则。

The governance layer structure is defined in:
governance/00_INDEX.md

本治理层结构定义见：
governance/00_INDEX.md

---

# 2. Architectural Invariants
# 2. 架构不变量

The following architectural principles must NEVER be violated:

以下架构原则不得被违反：

1. Tenant Isolation is mandatory.
   必须实现租户隔离。

2. Composite Foreign Keys must be enforced.
   必须使用复合外键约束。

3. Deterministic Execution only.
   执行必须确定性。

4. Governance overrides phase and application layers.
   治理层优先于阶段层与应用层。

If any implementation conflicts with these invariants,
the invariants take precedence.

如有冲突，以不变量为准。

---

# 3. Single Source of Truth (SSOT)
# 3. 单一事实来源定义

Each concern has a designated SSOT file.

每类规则必须有唯一权威来源。

---

## 3.1 Engineering Constraints
## 3.1 工程约束

SSOT:
governance/AGENTS.md

Defines:

- Coding constraints
- Automation constraints
- Codex behavior boundaries

定义：

- 编码约束
- 自动化约束
- Codex 行为边界

---

## 3.2 Product Milestones
## 3.2 产品里程碑

SSOT:
governance/ROADMAP.md

Defines:

- Phase progression
- Milestone boundaries
- Strategic direction

定义：

- 阶段推进
- 里程碑边界
- 战略方向

No other document may redefine milestone structure.

其他文件不得重新定义阶段边界。

---

## 3.3 Execution Workflow
## 3.3 执行流程

Reference document:
governance/EXECUTION_PLAYBOOK.md

This file defines workflow only.

本文件仅定义执行流程。

It does NOT define milestones or architectural invariants.

不定义里程碑或架构不变量。

If conflict exists with ROADMAP.md,
ROADMAP.md takes precedence.

如冲突，以 ROADMAP.md 为准。

---

## 3.4 Chat Interaction Rules
## 3.4 Chat 交互规则

SSOT:
governance/04_CHAT_INTERACTION_PROTOCOL.md

Defines:

- Mandatory alignment behavior
- “Based on” execution enforcement
- Scope discipline
- Deterministic interaction model

定义：

- 强制对齐规则
- Based on 执行规则
- 范围纪律
- 确定性交互模型

Chat behavior must comply with this file.

Chat 行为必须遵守本文件。

---

## 3.5 Execution Checkpoint State
## 3.5 执行检查点状态

SSOT:
phases/state.md

Defines:

- current_phase
- checkpoint/resume state
- last success/failure execution state

定义：

- 当前阶段
- 断点续跑状态
- 最近成功/失败执行状态

Synchronization view:
docs/PROJECT_STATUS.md

`docs/PROJECT_STATUS.md` is a human-readable mirrored status document.
It must stay synchronized with `phases/state.md`, but it is not the execution SSOT.

若两者不一致，以 `phases/state.md` 为执行准。

---

# 4. Phase Discipline
# 4. 阶段纪律

Phase blueprints must live in:

phases/phase-*.md

Phases define WHAT to implement.

阶段定义“做什么”。

They must not:

- Redefine architectural invariants
- Override SSOT mapping
- Modify governance silently

不得：

- 重定义架构不变量
- 覆盖 SSOT 规则
- 暗中修改治理文件

---

# 5. Conflict Resolution Rule
# 5. 冲突解决规则

If two documents conflict:

若两个文件冲突：

Priority order:

1. 01_GOVERNANCE.md
2. governance/ROADMAP.md
3. governance/AGENTS.md
4. governance/04_CHAT_INTERACTION_PROTOCOL.md
5. governance/EXECUTION_PLAYBOOK.md
6. phases/*.md
7. Application layer
8. Documentation layer

Higher layer overrides lower layer.

上层优先级高于下层。

---

# End of Document
# 文档结束
