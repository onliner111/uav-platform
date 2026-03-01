# UI Design System Baseline (Phase 26 WP2)

## 1. Scope
- Establish a stable design-token baseline for console UI pages.
- Standardize reusable primitive components for page headers, KPI cards, action rows, and status tags.
- Keep compatibility with existing templates while enabling incremental migration.

## 2. Token Baseline (`app/web/static/ui.css`)

### Typography Tokens
- `--font-xs`, `--font-sm`, `--font-md`, `--font-lg`, `--font-xl`

### Spacing Tokens
- `--space-1` .. `--space-6`

### Radius Tokens
- `--radius-sm`, `--radius-md`, `--radius-lg`, `--radius-xl`, `--radius-pill`

### Interaction Token
- `--focus-ring`

### Existing Semantic Color Tokens (continued)
- `--bg`, `--bg-alt`, `--panel`, `--ink`, `--muted`
- `--line`, `--line-strong`, `--accent`, `--accent-2`, `--accent-soft`
- `--danger`, `--success`

## 3. Primitive Component Classes
- `.ui-section-head`: standard panel header (title + actions)
- `.ui-section-subtitle`: semantic subtitle text style
- `.ui-action-row`: reusable action/button row container
- `.ui-field`: compact label/control stacking pattern
- `.ui-kpi-grid`: KPI card grid container
- `.ui-kpi-card`: standardized KPI card style
- `.status-pill.warn` / `.status-pill.danger`: status severity variants

## 4. Initial Adoption (WP2)
- KPI card standardization landed in:
  - `ui_console.html`
  - `ui_task_center.html`
  - `ui_assets.html`
  - `ui_compliance.html`
  - `ui_alerts.html`
  - `ui_reports.html`
  - `ui_platform.html`
- Section-head primitive adopted in:
  - `ui_compliance.html`
  - `ui_reports.html`

## 5. Interaction Pattern Baseline (WP3)
- Shared helper: `app/web/static/ui_action_helpers.js`
- Standardized interaction primitives:
  - Result severity rendering (`success` / `warn` / `danger`)
  - Busy-button handling during async writes
  - Unified error message normalization
- Adopted pages:
  - `task_center_ui.js` + `ui_task_center.html`
  - `assets_ui.js` + `ui_assets.html`
  - `alerts_ui.js` + `ui_alerts.html`

## 6. Migration Rule For Next WPs
- New UI pages must use design tokens instead of hardcoded sizes/radius/font sizes where practical.
- New KPI summary blocks should use `.ui-kpi-grid` + `.ui-kpi-card`.
- New panel headers with actions should prefer `.ui-section-head`.
- New write-action pages should use `window.UIActionUtils` for result state and busy interactions.
- Existing pages can migrate incrementally; avoid large one-shot restyling.
