# 00_INDEX.md
Documentation Index
文档索引与体系结构说明

---

# 1. Governance Layer 治理层

- governance/00_INDEX.md
- governance/01_GOVERNANCE.md
- governance/02_REPO_LAYOUT.md
- governance/03_PHASE_LIFECYCLE.md
- governance/04_CHAT_INTERACTION_PROTOCOL.md
- governance/05_GOVERNANCE_CONSISTENCY_CHECKLIST.md
- governance/tenant_boundary_matrix.md

Governance layer defines architectural invariants and structural constraints.
治理层定义架构不变量与结构性约束。

---

# 2. Repository SSOT Layer 单一事实来源层

- governance/AGENTS.md
- governance/ROADMAP.md
- governance/EXECUTION_PLAYBOOK.md

This layer defines:
- Engineering constraints
- Product milestones
- Execution workflow

本层定义：
- 工程约束
- 产品里程碑
- 执行流程

---

# 3. Phase Execution Layer 阶段执行层

- phases/index.md
- phases/phase-*.md
- phases/state.md
- phases/reporting.md

Phases define WHAT to implement.
阶段定义“做什么”。

---

# 4. Application & Infrastructure Layer 应用与基础设施层

- app/
- infra/
- tests/
- openapi/

This layer implements phase definitions.
本层实现阶段蓝图。

---

# 5. Reference & Manual Layer 文档说明层

- docs/Architecture_Overview_*.md
- docs/Deployment_Guide_*.md
- docs/Admin_Manual_*.md
- docs/User_Manual_*.md
- docs/API_Appendix_*.md

Human-readable documentation only.
仅供阅读说明。

---

# 6. Generated Reports 自动生成报告层

- logs/gpt_*.md

Generated reports are evidence artifacts, not SSOT.
生成报告属于证据文件，不是规则源。

---

# Phase Grouping Model 阶段分组模型

- Group A (Feature Delivery 功能交付): 01–06 (Completed)
- Group B (Structure Hardening 结构强化): 07–09 (In Progress)
- Group C (Production Readiness 生产就绪): 10–12 (Planned)

Execution checkpoint SSOT is phases/state.md; current active phase must be reflected in docs/PROJECT_STATUS.md.
执行检查点 SSOT 为 phases/state.md；当前执行阶段必须同步记录在 docs/PROJECT_STATUS.md。
