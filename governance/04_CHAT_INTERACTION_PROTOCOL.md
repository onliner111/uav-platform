# 04_CHAT_INTERACTION_PROTOCOL.md
Chat Interaction Governance Protocol
ChatGPT 交互治理协议

---

# 1. Purpose
# 1. 目的

This document defines behavioral constraints for ChatGPT interactions
within this repository.

本文件定义 ChatGPT 在本仓库中的交互行为约束。

It ensures:

- All execution guidance is traceable.
- No implicit architectural decisions are introduced.
- All actions remain aligned with governance and phase definitions.

确保：

- 所有执行建议可追溯来源。
- 不引入隐式架构决策。
- 所有行为与治理层与阶段定义保持一致。

---

# 2. Mandatory Alignment Rule
# 2. 强制对齐规则

Every new chat session MUST begin with alignment to:

每次新聊天必须对齐：

- governance/01_GOVERNANCE.md
- governance/02_REPO_LAYOUT.md
- governance/03_PHASE_LIFECYCLE.md
- governance/ROADMAP.md
- phases/state.md
- docs/PROJECT_STATUS.md

Optional (when relevant):

- governance/tenant_boundary_matrix.md
- phases/<current-phase-blueprint>.md

Execution-state ambiguity rule:

执行状态歧义规则：

If `phases/state.md` and `docs/PROJECT_STATUS.md` differ,
`phases/state.md` is authoritative for execution guidance.

No execution recommendation may be issued before alignment is confirmed.
未完成对齐前，不得给出执行建议。

---

# 3. “Based On” Execution Rule
# 3. “Based On” 执行规则

Any execution instruction provided by ChatGPT MUST explicitly state:

ChatGPT 提供的任何执行指令必须显式声明：

Based on: <specific file path>

Example:

Based on phases/phase-07c-tenant-export-purge.md,
implement the export service without modifying migrations.

Execution instructions without a source reference are invalid.
未引用来源文件的执行建议视为无效。

---

# 4. No Implicit Authority Rule
# 4. 禁止隐式权威规则

ChatGPT must NOT:

ChatGPT 不得：

- Redefine governance rules.
- Modify architectural invariants.
- Override phase definitions.
- Invent new execution standards.

If ambiguity exists, request clarification instead of assuming.

若存在歧义，应请求澄清，而非自行假设。

---

# 5. Phase Discipline Rule
# 5. 阶段纪律规则

ChatGPT must:

ChatGPT 必须：

- Stay within the scope of the current phase.
- Explicitly state if a recommendation exceeds phase scope.
- Never silently expand scope.

保持当前阶段范围内活动；
若超出范围必须明确说明。

---

# 6. Deterministic Guidance Rule
# 6. 确定性指导规则

When providing execution instructions:

在给出执行建议时必须：

- Avoid speculative design changes.
- Avoid vague language.
- Provide deterministic, file-scoped guidance.
- Clearly define allowed and forbidden modifications.

避免推测性设计修改；
避免模糊表达；
必须明确文件范围与限制。

---

# 7. Repository as SSOT Rule
# 7. 仓库单一事实来源原则

ChatGPT must not rely on prior chat memory as authoritative state.

ChatGPT 不得将历史聊天作为权威状态。

Only repository files define authoritative state.

仅仓库文件构成权威状态。

---

# 8. Governance Supremacy Rule
# 8. 治理优先原则

If any instruction conflicts with governance documents:

若指令与治理文件冲突：

Governance documents take precedence.
以治理文件为准。

---

# End of Document
# 文档结束
