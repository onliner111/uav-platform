# UI Page Inventory And PM Plan

## 1) Goal
- Maximize system capability usage through UI first.
- Turn API-first capabilities into role-oriented operation pages.
- Ensure all high-frequency workflows can be completed without manual API calls.

## 2) Current UI Inventory (Implemented vs Gap)

| Domain | Page | Route | Status | Evidence | Main Gap |
|---|---|---|---|---|---|
| Access | Login | `/ui/login` | Implemented | `app/web/templates/ui_login.html` | No MFA/session management page |
| Console | Workbench Home | `/ui/console` | Implemented | `app/web/templates/ui_console.html` | Needs customizable widgets/layout |
| Console | Global Shell + Nav | all `/ui/*` | Implemented | `app/web/templates/console_base.html`, `app/web/static/console_shell.js`, `app/web/static/ui.css` | IA still module-centric; role/task-centric flow needs phase 26 refinement |
| Observe | Command Center | `/ui/command-center` | Implemented | `app/web/templates/command_center.html` | Incident-centric drilldown and action panel depth still limited |
| Execute | Inspection List/Detail | `/ui/inspection`, `/ui/inspection/tasks/{id}` | Partial | `inspection_list.html`, `inspection_task_detail.html` | Task create/plan/batch action not fully UI-closed |
| Execute | Defect Workflow | `/ui/defects` | Partial | `app/web/templates/defects.html` | Assignment, SLA, batch transition, review actions incomplete |
| Execute | Emergency | `/ui/emergency` | Partial | `app/web/templates/emergency.html` | Incident command timeline and resource dispatch depth missing |
| Execute | Task Center | `/ui/task-center` | Partial+ | `app/web/templates/ui_task_center.html`, `app/web/static/task_center_ui.js` | Covers transition/dispatch quick actions; missing full create/edit/template workflow UI |
| Execute | Assets | `/ui/assets` | Partial+ | `app/web/templates/ui_assets.html`, `app/web/static/assets_ui.js` | Covers availability/health updates; maintenance workorders and lifecycle ops not fully UI-closed |
| Govern | Compliance | `/ui/compliance` | Partial | `app/web/templates/ui_compliance.html` | Mostly read/export; approval actions and policy editing are not complete |
| Govern | Alerts | `/ui/alerts` | Partial+ | `app/web/templates/ui_alerts.html`, `app/web/static/alerts_ui.js` | Covers ACK/CLOSE; shift/policy create-edit and escalation operation depth missing |
| Govern | Reports | `/ui/reports` | Partial | `app/web/templates/ui_reports.html` | Report generation/export workflows still API-led |
| Platform | Identity/Tenant Governance | `/ui/platform` | Partial | `app/web/templates/ui_platform.html` | Read-only heavy; user/role/org management write operations not productized |

## 3) High-Priority Missing UI Domains

| Domain | Needed Pages | Current Status |
|---|---|---|
| Outcome Operations | Raw uploads, outcome versions, lifecycle/retention, download center | Not implemented in UI |
| AI Governance | Model catalog, version promote/rollback, evaluation compare, rollout policy | Not implemented in UI |
| Commercial Ops | Billing plans, subscriptions, invoices, quota alerts | Not implemented in UI |
| Open Platform Ops | API credential/webhook management, callback logs, signature/security setup | Not implemented in UI |
| Reliability Ops | Observability overview, SLO center, backup/restore drill, security inspection, capacity planning | Not implemented in UI |

## 4) Product IA Recommendation (Role-Oriented)

### Global Nav Groups
- `Observe`: Command Center, Live Alerts, Realtime Map
- `Execute`: Task Center, Inspection, Defects, Emergency, Assets
- `Govern`: Compliance, Reports, Outcomes, AI Governance
- `Platform`: Identity, Tenant Ops, Billing, Open Platform, Reliability Ops

### Core User Roles
- Dispatcher: task, incident, asset dispatch pages
- Duty Officer: alert, escalation, SLA, shift pages
- Compliance Officer: approvals, airspace policy, preflight, decision records
- Data/AI Operator: outcomes, reporting, model governance pages
- Platform Admin: identity, billing, quota, integration, reliability pages

## 5) Phase-Based Delivery Plan (26-31)

| Phase | Main Objective | Key UI Deliverables |
|---|---|---|
| 26 | IA + Design System | Navigation regrouping, design tokens, common list/detail/action templates, RBAC visibility matrix, mobile/a11y baseline |
| 27 | Operations UI closure | Task/inspection/defect/emergency/assets write workflows fully UI-closed; cross-page action linkage |
| 28 | Compliance + Alert workbench | Approval center, airspace/prefight pages, alert duty desk, escalation operation, SLA/retro views |
| 29 | Data + AI governance UI | Outcomes hub, report center, AI model governance pages, evidence-chain visual trace |
| 30 | Commercial + platform ops UI | Billing/quota center, tenant operations, open-platform integration console |
| 31 | Observability + reliability console | Signals/SLO dashboard, backup-restore drill pages, security inspection, capacity forecast views |

## 6) UI Completion Definition (Per Page)
- Must support full happy path through UI for the page's primary workflow.
- Must provide explicit error handling and retry path.
- Must enforce RBAC at page level and action level.
- Must produce auditable action traces for write operations.
- Must pass responsive check (desktop + mobile key viewport).

