# PHASE 07A - Lookup Hardening Analysis

## Scope
- Scanned: `app/services/**`
- Patterns:
  - `session.get(...)`
  - `where(Model.id == ...)` without tenant filter
- Code changes: none

## Risk Rubric
- `LOW`: lookup is on a global/non-tenant table, or composite key already includes `tenant_id`.
- `MEDIUM`: lookup targets a tenant-scoped table but fetches by unscoped PK (`session.get`) and relies on post-fetch tenant checks.
- `HIGH`: tenant-scoped lookup missing tenant guard (not found in this scan).

## Replacement Patterns
- `R1` (tenant-scoped by id):
  - `select(Model).where(Model.tenant_id == tenant_id).where(Model.id == model_id)`
- `R2` (global by id):
  - `select(Model).where(Model.id == model_id)`
- `R3` (composite tenant key):
  - `select(UserRole).where(UserRole.tenant_id == tenant_id).where(UserRole.user_id == user_id).where(UserRole.role_id == role_id)`
- `R4` (role-permission with tenant guard):
  - `select(RolePermission).join(Role, Role.id == RolePermission.role_id).where(Role.tenant_id == tenant_id).where(RolePermission.role_id == role_id).where(RolePermission.permission_id == permission_id)`

## Summary
- `session.get(...)` hits: `51`
- `where(Model.id == ...)` hits without tenant filter: `0`
- Risk counts:
  - `MEDIUM`: 35
  - `LOW`: 16
  - `HIGH`: 0

## Detailed Hits (`session.get`)
| # | Location | Table | Tenant-Scoped? | Risk | Tenant-Safe Replacement |
|---|---|---|---|---|---|
| 1 | `app/services/registry_service.py:39` | `Tenant` | No (global) | LOW | `R2` |
| 2 | `app/services/defect_service.py:58` | `InspectionObservation` | Yes (`tenant_id`) | MEDIUM | `R1` |
| 3 | `app/services/defect_service.py:113` | `Defect` | Yes (`tenant_id`) | MEDIUM | `R1` |
| 4 | `app/services/defect_service.py:127` | `Defect` | Yes (`tenant_id`) | MEDIUM | `R1` |
| 5 | `app/services/defect_service.py:149` | `Defect` | Yes (`tenant_id`) | MEDIUM | `R1` |
| 6 | `app/services/defect_service.py:164` | `InspectionObservation` | Yes (`tenant_id`) | MEDIUM | `R1` |
| 7 | `app/services/defect_service.py:195` | `InspectionTask` | Yes (`tenant_id`) | MEDIUM | `R1` |
| 8 | `app/services/inspection_service.py:66` | `InspectionTemplate` | Yes (`tenant_id`) | MEDIUM | `R1` |
| 9 | `app/services/inspection_service.py:78` | `InspectionTemplate` | Yes (`tenant_id`) | MEDIUM | `R1` |
| 10 | `app/services/inspection_service.py:97` | `InspectionTemplate` | Yes (`tenant_id`) | MEDIUM | `R1` |
| 11 | `app/services/inspection_service.py:109` | `InspectionTemplate` | Yes (`tenant_id`) | MEDIUM | `R1` |
| 12 | `app/services/inspection_service.py:140` | `InspectionTask` | Yes (`tenant_id`) | MEDIUM | `R1` |
| 13 | `app/services/inspection_service.py:152` | `InspectionTask` | Yes (`tenant_id`) | MEDIUM | `R1` |
| 14 | `app/services/inspection_service.py:181` | `InspectionTask` | Yes (`tenant_id`) | MEDIUM | `R1` |
| 15 | `app/services/inspection_service.py:195` | `InspectionTask` | Yes (`tenant_id`) | MEDIUM | `R1` |
| 16 | `app/services/inspection_service.py:235` | `InspectionExport` | Yes (`tenant_id`) | MEDIUM | `R1` |
| 17 | `app/services/incident_service.py:70` | `Incident` | Yes (`tenant_id`) | MEDIUM | `R1` |
| 18 | `app/services/command_service.py:80` | `CommandRequestRecord` | Yes (`tenant_id`) | MEDIUM | `R1` |
| 19 | `app/services/command_service.py:109` | `Drone` | Yes (`tenant_id`) | MEDIUM | `R1` |
| 20 | `app/services/command_service.py:228` | `CommandRequestRecord` | Yes (`tenant_id`) | MEDIUM | `R1` |
| 21 | `app/services/identity_service.py:84` | `Tenant` | No (global) | LOW | `R2` |
| 22 | `app/services/identity_service.py:89` | `Tenant` | No (global) | LOW | `R2` |
| 23 | `app/services/identity_service.py:96` | `Tenant` | No (global) | LOW | `R2` |
| 24 | `app/services/identity_service.py:111` | `Tenant` | No (global) | LOW | `R2` |
| 25 | `app/services/identity_service.py:124` | `Tenant` | No (global) | LOW | `R2` |
| 26 | `app/services/identity_service.py:143` | `Tenant` | No (global) | LOW | `R2` |
| 27 | `app/services/identity_service.py:183` | `User` | Yes (`tenant_id`) | MEDIUM | `R1` |
| 28 | `app/services/identity_service.py:190` | `User` | Yes (`tenant_id`) | MEDIUM | `R1` |
| 29 | `app/services/identity_service.py:204` | `User` | Yes (`tenant_id`) | MEDIUM | `R1` |
| 30 | `app/services/identity_service.py:228` | `Role` | Yes (`tenant_id`) | MEDIUM | `R1` |
| 31 | `app/services/identity_service.py:235` | `Role` | Yes (`tenant_id`) | MEDIUM | `R1` |
| 32 | `app/services/identity_service.py:253` | `Role` | Yes (`tenant_id`) | MEDIUM | `R1` |
| 33 | `app/services/identity_service.py:277` | `Permission` | No (global) | LOW | `R2` |
| 34 | `app/services/identity_service.py:284` | `Permission` | No (global) | LOW | `R2` |
| 35 | `app/services/identity_service.py:302` | `Permission` | No (global) | LOW | `R2` |
| 36 | `app/services/identity_service.py:310` | `User` | Yes (`tenant_id`) | MEDIUM | `R1` |
| 37 | `app/services/identity_service.py:311` | `Role` | Yes (`tenant_id`) | MEDIUM | `R1` |
| 38 | `app/services/identity_service.py:314` | `UserRole` | Yes (PK includes `tenant_id`) | LOW | `R3` |
| 39 | `app/services/identity_service.py:321` | `User` | Yes (`tenant_id`) | MEDIUM | `R1` |
| 40 | `app/services/identity_service.py:322` | `Role` | Yes (`tenant_id`) | MEDIUM | `R1` |
| 41 | `app/services/identity_service.py:325` | `UserRole` | Yes (PK includes `tenant_id`) | LOW | `R3` |
| 42 | `app/services/identity_service.py:333` | `Role` | Yes (`tenant_id`) | MEDIUM | `R1` |
| 43 | `app/services/identity_service.py:334` | `Permission` | No (global) | LOW | `R2` |
| 44 | `app/services/identity_service.py:337` | `RolePermission` | Indirect (through `Role`) | LOW | `R4` |
| 45 | `app/services/identity_service.py:344` | `Role` | Yes (`tenant_id`) | MEDIUM | `R1` |
| 46 | `app/services/identity_service.py:345` | `Permission` | No (global) | LOW | `R2` |
| 47 | `app/services/identity_service.py:348` | `RolePermission` | Indirect (through `Role`) | LOW | `R4` |
| 48 | `app/services/identity_service.py:356` | `User` | Yes (`tenant_id`) | MEDIUM | `R1` |
| 49 | `app/services/alert_service.py:194` | `AlertRecord` | Yes (`tenant_id`) | MEDIUM | `R1` |
| 50 | `app/services/alert_service.py:209` | `AlertRecord` | Yes (`tenant_id`) | MEDIUM | `R1` |
| 51 | `app/services/alert_service.py:253` | `AlertRecord` | Yes (`tenant_id`) | MEDIUM | `R1` |

## Detailed Hits (`where(Model.id == ...)` without tenant filter)
No hits found.

Observed `where(Model.id == ...)` uses are tenant-filtered:
- `app/services/registry_service.py:31` (`Drone.tenant_id == tenant_id` + `Drone.id == drone_id`)
- `app/services/mission_service.py:47` (`Mission.tenant_id == tenant_id` + `Mission.id == mission_id`)
- `app/services/mission_service.py:54` (`Drone.tenant_id == tenant_id` + `Drone.id == drone_id`)

## Notes
- Tenant-scope determination is based on model definitions in `app/domain/models.py` (`tenant_id` presence and PK composition).
- No immediate `HIGH` findings were identified; existing code usually applies post-fetch tenant checks. This phase focuses on hardening those lookups to query-time tenant scoping.
