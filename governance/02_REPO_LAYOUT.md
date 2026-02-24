# 02_REPO_LAYOUT.md
Repository Structure & Placement Rules
仓库目录结构与放置规范

---

# 1. Purpose
# 1. 目的

This document defines the official directory structure of the uav-platform repository.

本文件定义 uav-platform 仓库的正式目录结构规范。

It clarifies:
- What goes where
- What must NOT go where
- Naming conventions
- Governance boundaries

它明确：
- 什么内容放在哪里
- 什么内容禁止放在哪里
- 命名规范
- 治理边界

All contributors (human or Codex) must follow this layout.
所有贡献者（包括人类与 Codex）必须遵循本规范。

---

# 2. Directory Responsibilities
# 2. 目录职责划分

---

## 2.1 governance/ — Governance Layer
## 2.1 governance/ —— 治理层

Defines system-wide invariants and architectural constraints.
定义系统级不变量与架构约束。

Contains / 包含：

- 00_INDEX.md
- 01_GOVERNANCE.md
- 02_REPO_LAYOUT.md
- 03_PHASE_LIFECYCLE.md
- 04_CHAT_INTERACTION_PROTOCOL.md
- 05_GOVERNANCE_CONSISTENCY_CHECKLIST.md
- ROADMAP.md
- EXECUTION_PLAYBOOK.md
- tenant_boundary_matrix.md
- AGENTS.md

Rules / 规则：

- Only modify when making deliberate architectural decisions.
  仅在明确架构决策时修改。

- Phase tasks must NOT silently change governance constraints.
  阶段任务不得暗中修改治理规则。

- Governance files override phase documents.
  治理文件优先级高于阶段文件。

---

## 2.2 phases/ — Phase Blueprint Layer
## 2.2 phases/ —— 阶段蓝图层

Defines WHAT to implement.
定义“做什么”。

Contains / 包含：

- phase-XX-master-blueprint.md
- phase-XX-subphase-*.md
- Acceptance criteria
- Scope definitions

Rules / 规则：

- Must define scope, constraints, exit criteria.
  必须定义范围、约束、退出条件。

- Must NOT contain execution logs.
  不得包含执行日志。

- Must NOT contain automation scripts.
  不得包含自动化脚本。

Naming convention:
phase-<number><optional-letter>-<short-name>.md

Example:
phase-07c-tenant-export-purge.md

---

## 2.3 docs/ — Documentation Layer
## 2.3 docs/ —— 文档说明层

Contains explanatory documentation for humans.
存放面向阅读者的说明文档。

Contains / 包含：

- PROJECT_STATUS.md
- CHAT_BOOTSTRAP.md
- Architecture overview
- User manuals
- Deployment guides

Rules / 规则：

- Describes system state and usage.
  描述系统状态与使用方法。

- Does NOT define governance rules.
  不定义治理规则。

- Does NOT contain executable scripts.
  不包含可执行脚本。

---

## 2.4 tooling/ — Automation Layer
## 2.4 tooling/ —— 自动化层

Contains automation utilities.
存放工程自动化工具。

Contains / 包含：

- Codex templates
- PowerShell scripts
- Validation scripts
- Report generators

Rules / 规则：

- No business logic.
  不得包含业务逻辑。

- No governance rules.
  不得包含治理规则。

- All automation must live here.
  所有自动化工具必须放在此目录。

---

## 2.5 app/ — Application Layer
## 2.5 app/ —— 应用层

Contains runtime domain logic.
存放业务运行代码。

Rules / 规则：

- No governance documentation.
- No phase blueprints.
- Only runtime application logic.

---

## 2.6 infra/ — Infrastructure Layer
## 2.6 infra/ —— 基础设施层

Contains:

- Docker configuration
- docker-compose
- Alembic migrations
- Environment configuration

Rules / 规则：

- Migrations must follow 3-step pattern:
  expand → backfill/validate → enforce

- No governance files.
  不得包含治理文件。

---

## 2.7 tests/ — Validation Layer
## 2.7 tests/ —— 验证层

Contains test cases.
存放测试代码。

Rules / 规则：

- Must enforce tenant isolation.
- Must validate composite FK rules.
- Must align with governance constraints.

---

## 2.8 logs/ — Log Layer
## 2.8 logs/ —— 日志层

Contains execution logs and artifacts.
存放执行日志与生成报告。

Rules / 规则：

- No authoritative architecture content.
- Can be cleaned periodically.

---

# 3. Root Directory Policy
# 3. 根目录规范

The root directory must remain minimal.
根目录必须保持精简。

Allowed / 允许：

- README.md
- Dockerfile
- docker-compose.yml
- Makefile
- pyproject.toml
- requirements*.txt

Not Allowed / 禁止：

- Phase blueprints
- Governance documents
- Execution scripts
- Architecture decisions

---

# 4. Architecture Layering Model
# 4. 架构分层模型

Governance Layer
        ↓
Phase Blueprint Layer
        ↓
Application Layer
        ↓
Infrastructure Layer
        ↓
Validation Layer

Governance overrides all layers.
治理层优先级最高。

---

# 5. Phase Completion Rule
# 5. 阶段完成规则

When a phase completes:

- Update docs/PROJECT_STATUS.md
- Preserve blueprint history
- Do NOT modify governance unless intentional

历史阶段文件属于不可删除记录。