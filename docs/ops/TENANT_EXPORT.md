# Tenant Export (Phase 07C-1)

This document describes the tenant-level export API delivered in Phase 07C-1.

## Scope

- Export is read-only.
- Export includes only tenant-scoped tables (tables with a `tenant_id` column).
- Global tables (for example `tenants`, `permissions`) are skipped and listed in `manifest.json`.
- Purge/delete is out of scope for this phase.

## API

- `POST /api/tenants/{tenant_id}/export?include_zip={true|false}`
  - Admin-only (`*` permission).
  - Returns: `export_id`, `status`, `manifest_path`, and optional `zip_path`.
- `GET /api/tenants/{tenant_id}/export/{export_id}`
  - Admin-only (`*` permission).
  - Returns manifest payload (table counts, hashes, metadata).
- `GET /api/tenants/{tenant_id}/export/{export_id}/download`
  - Admin-only (`*` permission).
  - Returns zip file when the export was created with `include_zip=true`.

Cross-tenant access keeps existing boundary semantics and returns `404`.

## Output Layout

Exports are written to:

`logs/exports/<tenant_id>/<export_id>/`

Artifacts:

- `manifest.json`
- `tables/<table_name>.jsonl`
- optional `<export_id>.zip`

## Local Run

1. Create tenant + bootstrap admin user via identity APIs.
2. Login via `/api/identity/dev-login` to get a bearer token.
3. Trigger export:

```bash
curl -X POST "http://localhost:8000/api/tenants/<tenant_id>/export?include_zip=true" \
  -H "Authorization: Bearer <token>"
```

4. Check status:

```bash
curl "http://localhost:8000/api/tenants/<tenant_id>/export/<export_id>" \
  -H "Authorization: Bearer <token>"
```

5. Download zip:

```bash
curl -L "http://localhost:8000/api/tenants/<tenant_id>/export/<export_id>/download" \
  -H "Authorization: Bearer <token>" \
  -o tenant-export.zip
```
