# 05_GOVERNANCE_CONSISTENCY_CHECKLIST.md
Global Governance Consistency Self-Check
全局治理一致性自检表

---

# 1. Purpose
# 1. 目的

This checklist ensures that governance, phase execution,
application implementation, and documentation remain aligned.

本自检表用于确保治理层、阶段执行、应用实现与文档说明保持一致。

Use this document:

在以下情况必须使用本自检表：

- Before starting a new major phase
- After completing a phase
- Before architectural refactoring
- Before production release

---

# 2. Governance Layer Consistency
# 2. 治理层一致性

[ ] governance/01_GOVERNANCE.md reflects current architectural invariants  
[ ] governance/02_REPO_LAYOUT.md matches actual repository structure  
[ ] governance/03_PHASE_LIFECYCLE.md aligns with phase workflow  
[ ] governance/04_CHAT_INTERACTION_PROTOCOL.md enforced in new chats  
[ ] governance/ROADMAP.md matches real milestone progression  
[ ] governance/tenant_boundary_matrix.md is up-to-date  

If any mismatch is detected, governance must be updated deliberately.
若发现不一致，必须通过明确决策更新治理文件。

---

# 3. Phase Alignment
# 3. 阶段一致性

[ ] docs/PROJECT_STATUS.md reflects current active phase  
[ ] phases/state.md correctly indicates execution state  
[ ] If the two files differ, phases/state.md is treated as execution SSOT and PROJECT_STATUS.md is synced  
[ ] Completed phases are preserved and immutable  
[ ] Current phase scope does not exceed blueprint definition  

No phase may redefine governance.
阶段不得重定义治理规则。

---

# 4. Application & Infrastructure Integrity
# 4. 应用与基础设施完整性

[ ] Tenant isolation is enforced  
[ ] Composite foreign key constraints are preserved  
[ ] Migrations follow expand → backfill → enforce pattern  
[ ] Tests validate governance constraints  
[ ] No cross-tenant leakage possible  

---

# 5. Documentation Accuracy
# 5. 文档准确性

[ ] User manuals reflect actual API behavior  
[ ] Deployment guides match real infrastructure setup  
[ ] Deprecated documents clearly marked  
[ ] No document contradicts governance layer  

Documentation is descriptive, not authoritative for rules.
文档说明层不具有治理权威。

---

# 6. Automation & Execution Integrity
# 6. 自动化与执行完整性

[ ] EXECUTION_PLAYBOOK.md defines workflow only  
[ ] Milestones defined only in governance/ROADMAP.md and phases/  
[ ] Codex executions reference specific phase documents  
[ ] All execution instructions include “Based on” reference  

---

# 7. Layering Integrity Model
# 7. 分层完整性模型

Governance Layer
        ↓
Phase Blueprint Layer
        ↓
Application Layer
        ↓
Infrastructure Layer
        ↓
Validation Layer
        ↓
Documentation Layer

Governance overrides all layers.
治理层优先级最高。

Lower layers must not contradict upper layers.
下层不得违反上层规则。

---

# 8. Final Release Gate
# 8. 最终发布门禁

Before production release:

生产发布前必须：

[ ] All above checks verified  
[ ] PROJECT_STATUS.md updated  
[ ] No governance violations detected  
[ ] No unresolved tenant boundary gaps  

If any item fails, release must be blocked.
如存在未通过项，必须阻止发布。

---

# End of Document
# 文档结束
