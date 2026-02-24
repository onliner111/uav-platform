# Identity Boundary Confirmation (Phase 07A C4)

Basis:
- `phases/phase-07a-lookup-hardening-execution-plan.md` (C4 scope: `User`/`Role` tenant-scoped lookups)
- `app/domain/models.py`
- `app/services/identity_service.py`

## Model Boundary Matrix

| Model | 1) Tenant-scoped or global? | 2) Includes `tenant_id`? | 3) Is `session.get(...)` usage safe? | 4) Composite PK already safe? | 5) Remaining id-only risk? |
|---|---|---|---|---|---|
| `Tenant` | Global identity root table | No | Yes for boundary purposes (`session.get(Tenant, id)` is global lookup, not cross-tenant object access) | N/A | No tenant-boundary id-only risk in identity service |
| `User` | Tenant-scoped | Yes (`tenant_id` FK) | Raw `session.get(User, id)` is not safe for tenant isolation; C4 replaced user lookups with tenant-scoped selects (`tenant_id` + `id`) | No (PK is `id` only) | No remaining id-only `session.get(User, ...)` in `identity_service.py` |
| `Role` | Tenant-scoped | Yes (`tenant_id` FK) | Raw `session.get(Role, id)` is not safe for tenant isolation; C4 replaced role lookups with tenant-scoped selects (`tenant_id` + `id`) | No (PK is `id` only) | No remaining id-only `session.get(Role, ...)` in `identity_service.py` |
| `Permission` | Global catalog table | No | Yes (`session.get(Permission, id)` is global by design) | No (PK is `id` only) | No tenant-boundary id-only risk |
| `UserRole` | Tenant-scoped association | Yes (`tenant_id`) | Yes when called as `session.get(UserRole, (tenant_id, user_id, role_id))` | Yes (composite PK includes `tenant_id`) | No meaningful id-only risk in current identity service usage |
| `RolePermission` | Indirectly tenant-scoped through `Role` (plus global `Permission`) | No | Conditionally safe: `session.get(RolePermission, (role_id, permission_id))` is safe when preceded by tenant-scoped `Role` validation | Partially: composite PK exists, but does not include `tenant_id` | Low residual design risk if any future caller skips tenant-scoped `Role` guard |

## Evidence Notes

- `User` and `Role` are tenant-scoped tables with `id` PK plus `tenant_id`, and unique constraints on (`tenant_id`, `id`): `app/domain/models.py`.
- `UserRole` PK is (`tenant_id`, `user_id`, `role_id`) with composite FKs to tenant-qualified `users` and `roles`: `app/domain/models.py`.
- `RolePermission` PK is (`role_id`, `permission_id`) and has no `tenant_id`; tenant boundary must come from a tenant-scoped role check: `app/domain/models.py`.
- In `IdentityService`, `User`/`Role` id-only gets are replaced by `_get_scoped_user(...)` / `_get_scoped_role(...)` tenant filters: `app/services/identity_service.py`.
