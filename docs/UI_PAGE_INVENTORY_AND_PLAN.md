# UI 页面清单与产品规划（更新至 Phase 39）

## 1) 文档目标（Goal）
- 优先通过 UI 释放系统能力，而不是依赖手工调用 API。
- 将 API-first 能力转成面向角色的操作页面。
- 确保高频流程可通过页面完成。
- 保持所有用户可见页面不低于 Phase 32 的产品化基线。

## 2) 当前 UI 清单（已实现情况与产品状态）

| Domain | Page | Route | Status | Evidence | Main Gap |
|---|---|---|---|---|---|
| Access | Login | `/ui/login` | Implemented | `app/web/templates/ui_login.html` | MFA and richer session-security UX are still not productized |
| Console | Workbench Home | `/ui/console` | Productized | `app/web/templates/ui_console.html` | Personalized widget customization is still light |
| Console | Global Shell + Nav | all `/ui/*` | Productized | `app/web/templates/console_base.html`, `app/web/static/console_shell.js`, `app/web/static/ui.css` | Secondary admin IA can still be refined further if needed |
| Observe | Command Center | `/ui/command-center` | Productized | `app/web/templates/command_center.html` | Real video and deep incident dispatch still depend on later real-integration phases |
| Execute | Inspection List/Detail | `/ui/inspection`, `/ui/inspection/tasks/{id}` | Productized | `inspection_list.html`, `inspection_task_detail.html` | Batch planning and true field-device integration can go deeper |
| Execute | Defect Workflow | `/ui/defects` | Productized | `app/web/templates/defects.html` | Cross-team SLA automation can still be enhanced |
| Execute | Emergency | `/ui/emergency` | Productized | `app/web/templates/emergency.html` | Real-world resource dispatch depth still depends on later hardware integration |
| Execute | Task Center | `/ui/task-center` | Productized | `app/web/templates/ui_task_center.html`, `app/web/static/task_center_ui.js` | Advanced planning/template authoring can still be expanded |
| Execute | Assets | `/ui/assets` | Productized | `app/web/templates/ui_assets.html`, `app/web/static/assets_ui.js` | Real dock/airport control is not yet integrated |
| Govern | Compliance | `/ui/compliance` | Productized | `app/web/templates/ui_compliance.html` | Advanced compliance authoring still intentionally stays admin-oriented |
| Govern | Alerts | `/ui/alerts` | Productized | `app/web/templates/ui_alerts.html`, `app/web/static/alerts_ui.js` | Real external notification-channel rollout still depends on deployment context |
| Govern | Reports | `/ui/reports` | Productized | `app/web/templates/ui_reports.html`, `app/web/static/reports_ui.js` | Deep reporting templates and customer-specific variants can still expand |
| Platform | Release / Onboarding Ops | `/ui/platform` | Productized | `app/web/templates/ui_platform.html`, `app/web/static/platform_ui.js` | Real rollout validation still depends on future pilot projects |
| Admin Special | Observability / Reliability / AI / Commercial / Open Platform | `/ui/observability`, `/ui/reliability`, `/ui/ai-governance`, `/ui/commercial-ops`, `/ui/open-platform` | Implemented + Admin Productized | corresponding templates + scripts in `app/web` | Still admin-specialized; not intended as broad business-user main path |

## 3) 当前高优先级缺口（截至 Phase 39）

| Domain | Needed Pages | Current Status |
|---|---|---|
| Real UAV Integration | Real-mode connection diagnostics, explicit Fake/Sim/Real UX, field-ready connection guidance | Planned in Phase 40 |
| Dock / Airport Control | Dock state, hatch/power actions, manual takeover, task linkage | Planned in Phase 41 |
| Media Engineering | Stable video-state UX, degradation guidance, operator-facing stream diagnostics | Planned in Phase 42 |
| Pilot Rollout Validation | Trial checklists, real-user training flows, issue capture, rollout feedback console | Planned in Phase 43 |
| Customer-Specific Extensions | Industry templates, tenant-specific workflows, localized reporting variants | Not started; should follow pilot validation |

## 4) 当前 IA 结论（角色导向）

### 全局导航分组（Global Nav Groups）
- `Observe`: Command Center, Live Alerts, Realtime Map
- `Execute`: Task Center, Inspection, Defects, Emergency, Assets
- `Govern`: Compliance, Reports, Outcomes, AI Governance
- `Platform`: Identity, Tenant Ops, Billing, Open Platform, Reliability Ops

### 核心用户角色（Core User Roles）
- Dispatcher: task, incident, asset dispatch pages
- Duty Officer: alert, escalation, SLA, shift pages
- Compliance Officer: approvals, airspace policy, preflight, decision records
- Data/AI Operator: outcomes, reporting, model governance pages
- Platform Admin: identity, billing, quota, integration, reliability pages

状态说明：
- 角色导向 IA 已通过 Phase 32-39 基本落地。
- 当前剩余重点已不再是“核心 IA 搭建”，而是“真实接入与试点验证”。

## 5) 已交付阶段映射（26-39）

| Phase | Main Objective | Key UI Deliverables |
|---|---|---|
| 26 | IA + Design System | Navigation regrouping, design tokens, common list/detail/action templates, RBAC visibility matrix, mobile/a11y baseline |
| 27 | Operations UI closure | Task/inspection/defect/emergency/assets write workflows fully UI-closed; cross-page action linkage |
| 28 | Compliance + Alert workbench | Approval center, airspace / preflight pages, alert duty desk, escalation operation, SLA / retro views |
| 29 | Data + AI governance UI | Outcomes hub, report center, AI model governance pages, evidence-chain visual trace |
| 30 | Commercial + platform ops UI | Billing/quota center, tenant operations, open-platform integration console |
| 31 | Observability + reliability console | Signals/SLO dashboard, backup-restore drill pages, security inspection, capacity forecast views |
| 32 | Role workbench productization | Role-based workbench home, Chinese shell, admin-special IA, page-wide productization baseline |
| 33 | One-map command center v2 | Mode switching, focus object, timeline linkage, one-map duty shell |
| 34 | Guided workflows | Inspection and emergency three-step wizards, compliance flow visualization |
| 35 | Mobile field operations | Mobile-first field execution and defects pages, weak-network guidance |
| 36 | Closure outcomes consumption | Business closure board, review workbench, leadership reporting |
| 37 | Notification collaboration hub | Message center, unified to-do, channel strategy, escalation tracking |
| 38 | Delivery onboarding operations | Tenant onboarding wizard, config packs, handoff panels |
| 39 | Release adoption lifecycle | Release checklist, help center, release notes, gray-enable guidance |

## 6) 后续与 UI 相关的规划（40-43）

| Phase | Main Objective | Key UI / UX Impact |
|---|---|---|
| 40 | Real UAV integration hardening | Clear Fake/Sim/Real state, real-device diagnostics, admin-safe connection guidance |
| 41 | Dock / airport control integration | Dock state cards, safe action confirmations, manual takeover UX |
| 42 | Media stream engineering | Stable video-state UX, degradation messaging, stream-health guidance |
| 43 | Pilot rollout validation | Trial checklists, training aids, real-user issue capture and rollout feedback |

## 7) 页面完成标准（Per Page）
- 页面必须支持主流程的完整 happy path。
- 页面必须提供明确的错误处理和重试路径。
- 页面必须在页面级和动作级执行 RBAC 控制。
- 页面写操作必须产生可审计痕迹。
- 页面必须通过桌面端和移动端关键视口检查。
- 业务用户页面必须让非技术用户可理解，不能依赖手工 API 调用或原始技术字段。
