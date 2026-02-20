# AGENTS.md — Autonomous Engineering Rules (Standard Edition)

本文件定义 Codex 在本仓库中的长期行为规则。
目标是：最大化自动执行，最小化人工参与。

---

# 1️ 项目定位（Project Goal）

本项目为“城市低空综合治理与应急指挥平台”。

当前主线：
- B 城管巡查（高频使用）
- A 应急指挥（展示能力）

开发方式：
- 单体 FastAPI
- 插件式 Adapter
- 容器化运行
- 分阶段（Phase）推进

---

# 2️ 核心原则（Core Principles）

## Phase Discipline
- MUST implement ONLY the current phase.
- MUST NOT implement future phases early.
- MUST strictly follow phases/*.md specification.

## Architecture Constraint
- MUST keep monolith + plugin adapters.
- MUST NOT introduce microservices.
- MUST NOT introduce Node/Vite/React unless phase explicitly requires.
- MUST NOT add new infrastructure services unless explicitly required.

## Containerization
- All commands MUST run via docker compose / Makefile.
- MUST NOT rely on host Python/Node.

## Quality Gate (Hard Requirement)
Before declaring success, MUST pass:

- make lint
- make typecheck
- make test
- make e2e (if exists)

If any fails:
- Auto-fix within scope.
- Retry up to 3 fix cycles.
- If still failing, STOP and output:
  - failing command
  - key error excerpt
  - minimal required human action

---

# 3️ 自动执行策略（Autonomy Strategy）

- Do NOT ask questions unless strictly blocking.
- Prefer simplest viable implementation.
- Avoid over-engineering.
- No speculative optimization.
- No large refactors.
- MUST follow phases/reporting.md after each phase (success or failure).

目标是：
稳定推进，而不是架构炫技。

---

# 4️ 输出规范（Minimal Output Policy）

完成阶段后，只输出：

1) What was delivered（1-2 段说明）
2) How to verify（精确命令）
3) Risks / Notes（<= 5 条）

禁止输出：
- 长篇解释
- 设计辩论
- 文件计划（File Plan）
- 过多内部推理

---

# 5️ 数据与权限规则（Government Mode）

- All new tables MUST include tenant_id.
- MUST enforce tenant isolation in queries.
- MUST integrate with existing RBAC.
- MUST log critical actions into audit_log.

关键操作包括：
- 任务创建
- 应急任务
- 指令下发
- 数据导出
- 审批动作

---

# 6️ 前端规则（UI Discipline）

- Lightweight embedded UI only (Jinja2 + static JS).
- Leaflet CDN allowed.
- No frontend build pipeline.
- UI must be demo-ready.

---

# 7️ 事件与告警规则（Event Integrity）

- Business state changes MUST generate events.
- Alerts MUST be persisted.
- No real-time control logic handled by LLM.
- Platform logic must remain deterministic.

---

# 8️ 禁止事项（Strict Prohibitions）

MUST NOT:

- Change docker-compose structure unless phase demands.
- Replace database.
- Introduce message queue prematurely.
- Remove existing modules.
- Break e2e flow.

---

# 9️ 阶段启动方式（Execution Entry）

Codex should always execute:

Execute phases/<phase-name>.md strictly.

No deviation allowed.

---

# 10 长期演进原则（Long-term Evolution）

- Optimize only when required by scale.
- Defer architecture complexity.
- Business first, architecture second.
- Demo ability is mandatory.
- Acceptance readiness is mandatory.

---

# Final Rule

Stability > Elegance  
Execution > Discussion  
Delivery > Refactor

---

# 11️ Checkpoint / Resume (Required)

- MUST treat phases/state.md as the single source of truth for resume.
- On start:
  1) Read phases/state.md
  2) Determine current_phase
  3) Execute only from current_phase onward following phases/index.md order
- On phase success:
  - Update phases/state.md:
    - last_success_phase
    - current_phase -> next phase (or DONE)
    - status
    - updated_at
- On phase failure (after max 3 fix cycles):
  - Update phases/state.md:
    - last_failure_phase
    - status=FAILED
    - last_error (short excerpt)
    - updated_at
  - STOP.