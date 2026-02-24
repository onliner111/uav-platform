# Tenant Purge (Phase 07C-2 / 07C-3)

This document describes tenant-level purge APIs:

- dry-run planning (`07C-2`)
- execute purge with safety rails (`07C-3`)

## Scope

- Purge targets tenant-scoped tables (tables with `tenant_id`) plus linkage tables
  that reference tenant-owned rows (for example `role_permissions`).
- Deletion order follows dependency plan (leaf -> parent).
- Cross-tenant access keeps existing boundary semantics and returns `404`.
- Purge requires a dry-run first and confirmation (`confirm_token` or `confirm_phrase`).

## API

- `POST /api/tenants/{tenant_id}/purge:dry_run`
  - Admin-only (`*` permission).
  - Returns table deletion plan, per-table counts, estimated rows, and `confirm_token`.
  - Persists dry-run snapshot to `logs/purge/<tenant_id>/<dry_run_id>/dry_run.json`.

- `POST /api/tenants/{tenant_id}/purge`
  - Admin-only (`*` permission).
  - Request body:
    - `dry_run_id` (required)
    - `confirm_token` (optional)
    - `confirm_phrase` (optional; exact value: `I_UNDERSTAND_THIS_WILL_DELETE_TENANT_DATA`)
    - `mode` (must be `hard`)
  - Executes tenant purge and writes report:
    - `logs/purge/<tenant_id>/<purge_id>/report.json`

- `GET /api/tenants/{tenant_id}/purge/{purge_id}`
  - Admin-only (`*` permission).
  - Returns persisted purge report payload.

## Output Layout

- Dry-run: `logs/purge/<tenant_id>/<dry_run_id>/dry_run.json`
- Execute report: `logs/purge/<tenant_id>/<purge_id>/report.json`

## Local Run

1. Create tenant and bootstrap admin via identity APIs.
2. Login using `/api/identity/dev-login`.
3. Run dry-run:

```bash
curl -X POST "http://localhost:8000/api/tenants/<tenant_id>/purge:dry_run" \
  -H "Authorization: Bearer <token>"
```

4. Execute purge with token:

```bash
curl -X POST "http://localhost:8000/api/tenants/<tenant_id>/purge" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"dry_run_id":"<dry_run_id>","confirm_token":"<confirm_token>","mode":"hard"}'
```

5. Read purge report:

```bash
curl "http://localhost:8000/api/tenants/<tenant_id>/purge/<purge_id>" \
  -H "Authorization: Bearer <token>"
```
