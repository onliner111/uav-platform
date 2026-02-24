from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.api.deps import get_current_claims, require_perm
from app.domain.models import (
    BootstrapAdminRequest,
    DataAccessPolicyRead,
    DataAccessPolicyUpdate,
    DevLoginRequest,
    OrgUnitCreate,
    OrgUnitRead,
    OrgUnitUpdate,
    PermissionCreate,
    PermissionRead,
    PermissionUpdate,
    RoleCreate,
    RoleFromTemplateCreateRequest,
    RoleRead,
    RoleTemplateRead,
    RoleUpdate,
    TenantCreate,
    TenantRead,
    TenantUpdate,
    TokenResponse,
    UserCreate,
    UserOrgMembershipBindRequest,
    UserOrgMembershipLinkRead,
    UserRead,
    UserRoleBatchBindRead,
    UserRoleBatchBindRequest,
    UserUpdate,
)
from app.domain.permissions import PERM_IDENTITY_READ, PERM_IDENTITY_WRITE
from app.infra.audit import set_audit_context
from app.infra.auth import create_access_token
from app.services.identity_service import AuthError, ConflictError, IdentityService, NotFoundError

router = APIRouter()


def get_identity_service() -> IdentityService:
    return IdentityService()


Claims = Annotated[dict[str, Any], Depends(get_current_claims)]
Service = Annotated[IdentityService, Depends(get_identity_service)]


def _handle_identity_error(exc: Exception) -> None:
    if isinstance(exc, NotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if isinstance(exc, ConflictError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if isinstance(exc, AuthError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    raise exc


def _policy_snapshot(policy: Any) -> dict[str, Any]:
    scope_mode = getattr(policy.scope_mode, "value", policy.scope_mode)
    return {
        "scope_mode": str(scope_mode),
        "org_unit_ids": list(policy.org_unit_ids),
        "project_codes": list(policy.project_codes),
        "area_codes": list(policy.area_codes),
        "task_ids": list(policy.task_ids),
    }


def _set_scope_deny_audit(
    request: Request,
    *,
    action: str,
    reason: str,
    target: dict[str, Any] | None = None,
) -> None:
    detail: dict[str, Any] = {"result": {"outcome": "denied", "reason": reason}}
    if target is not None:
        detail["what"] = {"target": target}
    set_audit_context(request, action=action, detail=detail)


@router.post("/tenants", response_model=TenantRead, status_code=status.HTTP_201_CREATED)
def create_tenant(payload: TenantCreate, service: Service) -> TenantRead:
    try:
        tenant = service.create_tenant(payload)
        return TenantRead.model_validate(tenant)
    except (NotFoundError, ConflictError, AuthError) as exc:
        _handle_identity_error(exc)
        raise


@router.get(
    "/tenants",
    response_model=list[TenantRead],
    dependencies=[Depends(require_perm(PERM_IDENTITY_READ))],
)
def list_tenants(claims: Claims, service: Service) -> list[TenantRead]:
    tenants = service.list_tenants(claims["tenant_id"])
    return [TenantRead.model_validate(item) for item in tenants]


@router.get(
    "/tenants/{tenant_id}",
    response_model=TenantRead,
    dependencies=[Depends(require_perm(PERM_IDENTITY_READ))],
)
def get_tenant(tenant_id: str, claims: Claims, service: Service) -> TenantRead:
    if claims["tenant_id"] != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="tenant not found")
    try:
        tenant = service.get_tenant(tenant_id)
        return TenantRead.model_validate(tenant)
    except (NotFoundError, ConflictError, AuthError) as exc:
        _handle_identity_error(exc)
        raise


@router.patch(
    "/tenants/{tenant_id}",
    response_model=TenantRead,
    dependencies=[Depends(require_perm(PERM_IDENTITY_WRITE))],
)
def update_tenant(tenant_id: str, payload: TenantUpdate, claims: Claims, service: Service) -> TenantRead:
    if claims["tenant_id"] != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="tenant not found")
    try:
        tenant = service.update_tenant(tenant_id, payload)
        return TenantRead.model_validate(tenant)
    except (NotFoundError, ConflictError, AuthError) as exc:
        _handle_identity_error(exc)
        raise


@router.delete(
    "/tenants/{tenant_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_perm(PERM_IDENTITY_WRITE))],
)
def delete_tenant(tenant_id: str, claims: Claims, service: Service) -> Response:
    if claims["tenant_id"] != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="tenant not found")
    try:
        service.delete_tenant(tenant_id)
    except (NotFoundError, ConflictError, AuthError) as exc:
        _handle_identity_error(exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/bootstrap-admin", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def bootstrap_admin(payload: BootstrapAdminRequest, service: Service) -> UserRead:
    try:
        user = service.bootstrap_admin(payload)
        return UserRead.model_validate(user)
    except (NotFoundError, ConflictError, AuthError) as exc:
        _handle_identity_error(exc)
        raise


@router.post("/dev-login", response_model=TokenResponse)
def dev_login(payload: DevLoginRequest, service: Service) -> TokenResponse:
    try:
        user, permissions = service.dev_login(payload.tenant_id, payload.username, payload.password)
    except (NotFoundError, ConflictError, AuthError) as exc:
        _handle_identity_error(exc)
        raise
    token = create_access_token(
        user_id=user.id,
        tenant_id=user.tenant_id,
        permissions=permissions,
    )
    return TokenResponse(access_token=token, permissions=permissions)


@router.post(
    "/users",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_perm(PERM_IDENTITY_WRITE))],
)
def create_user(payload: UserCreate, claims: Claims, service: Service) -> UserRead:
    try:
        user = service.create_user(claims["tenant_id"], payload)
        return UserRead.model_validate(user)
    except (NotFoundError, ConflictError, AuthError) as exc:
        _handle_identity_error(exc)
        raise


@router.get(
    "/users",
    response_model=list[UserRead],
    dependencies=[Depends(require_perm(PERM_IDENTITY_READ))],
)
def list_users(claims: Claims, service: Service) -> list[UserRead]:
    users = service.list_users(claims["tenant_id"])
    return [UserRead.model_validate(item) for item in users]


@router.get(
    "/users/{user_id}",
    response_model=UserRead,
    dependencies=[Depends(require_perm(PERM_IDENTITY_READ))],
)
def get_user(user_id: str, claims: Claims, service: Service) -> UserRead:
    try:
        user = service.get_user(claims["tenant_id"], user_id)
        return UserRead.model_validate(user)
    except (NotFoundError, ConflictError, AuthError) as exc:
        _handle_identity_error(exc)
        raise


@router.patch(
    "/users/{user_id}",
    response_model=UserRead,
    dependencies=[Depends(require_perm(PERM_IDENTITY_WRITE))],
)
def update_user(user_id: str, payload: UserUpdate, claims: Claims, service: Service) -> UserRead:
    try:
        user = service.update_user(claims["tenant_id"], user_id, payload)
        return UserRead.model_validate(user)
    except (NotFoundError, ConflictError, AuthError) as exc:
        _handle_identity_error(exc)
        raise


@router.delete(
    "/users/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_perm(PERM_IDENTITY_WRITE))],
)
def delete_user(user_id: str, claims: Claims, service: Service) -> Response:
    try:
        service.delete_user(claims["tenant_id"], user_id)
    except (NotFoundError, ConflictError, AuthError) as exc:
        _handle_identity_error(exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/roles",
    response_model=RoleRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_perm(PERM_IDENTITY_WRITE))],
)
def create_role(payload: RoleCreate, claims: Claims, service: Service) -> RoleRead:
    try:
        role = service.create_role(claims["tenant_id"], payload)
        return RoleRead.model_validate(role)
    except (NotFoundError, ConflictError, AuthError) as exc:
        _handle_identity_error(exc)
        raise


@router.get(
    "/roles",
    response_model=list[RoleRead],
    dependencies=[Depends(require_perm(PERM_IDENTITY_READ))],
)
def list_roles(claims: Claims, service: Service) -> list[RoleRead]:
    roles = service.list_roles(claims["tenant_id"])
    return [RoleRead.model_validate(item) for item in roles]


@router.get(
    "/roles/{role_id}",
    response_model=RoleRead,
    dependencies=[Depends(require_perm(PERM_IDENTITY_READ))],
)
def get_role(role_id: str, claims: Claims, service: Service) -> RoleRead:
    try:
        role = service.get_role(claims["tenant_id"], role_id)
        return RoleRead.model_validate(role)
    except (NotFoundError, ConflictError, AuthError) as exc:
        _handle_identity_error(exc)
        raise


@router.patch(
    "/roles/{role_id}",
    response_model=RoleRead,
    dependencies=[Depends(require_perm(PERM_IDENTITY_WRITE))],
)
def update_role(role_id: str, payload: RoleUpdate, claims: Claims, service: Service) -> RoleRead:
    try:
        role = service.update_role(claims["tenant_id"], role_id, payload)
        return RoleRead.model_validate(role)
    except (NotFoundError, ConflictError, AuthError) as exc:
        _handle_identity_error(exc)
        raise


@router.delete(
    "/roles/{role_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_perm(PERM_IDENTITY_WRITE))],
)
def delete_role(role_id: str, claims: Claims, service: Service) -> Response:
    try:
        service.delete_role(claims["tenant_id"], role_id)
    except (NotFoundError, ConflictError, AuthError) as exc:
        _handle_identity_error(exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/role-templates",
    response_model=list[RoleTemplateRead],
    dependencies=[Depends(require_perm(PERM_IDENTITY_READ))],
)
def list_role_templates(service: Service) -> list[RoleTemplateRead]:
    rows = service.list_role_templates()
    return [RoleTemplateRead.model_validate(item) for item in rows]


@router.post(
    "/roles:from-template",
    response_model=RoleRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_perm(PERM_IDENTITY_WRITE))],
)
def create_role_from_template(
    payload: RoleFromTemplateCreateRequest,
    claims: Claims,
    service: Service,
) -> RoleRead:
    try:
        role = service.create_role_from_template(
            tenant_id=claims["tenant_id"],
            template_key=payload.template_key,
            name=payload.name,
        )
        return RoleRead.model_validate(role)
    except (NotFoundError, ConflictError, AuthError) as exc:
        _handle_identity_error(exc)
        raise


@router.post(
    "/org-units",
    response_model=OrgUnitRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_perm(PERM_IDENTITY_WRITE))],
)
def create_org_unit(payload: OrgUnitCreate, claims: Claims, service: Service) -> OrgUnitRead:
    try:
        org_unit = service.create_org_unit(claims["tenant_id"], payload)
        return OrgUnitRead.model_validate(org_unit)
    except (NotFoundError, ConflictError, AuthError) as exc:
        _handle_identity_error(exc)
        raise


@router.get(
    "/org-units",
    response_model=list[OrgUnitRead],
    dependencies=[Depends(require_perm(PERM_IDENTITY_READ))],
)
def list_org_units(claims: Claims, service: Service) -> list[OrgUnitRead]:
    units = service.list_org_units(claims["tenant_id"])
    return [OrgUnitRead.model_validate(item) for item in units]


@router.get(
    "/org-units/{org_unit_id}",
    response_model=OrgUnitRead,
    dependencies=[Depends(require_perm(PERM_IDENTITY_READ))],
)
def get_org_unit(org_unit_id: str, claims: Claims, service: Service) -> OrgUnitRead:
    try:
        org_unit = service.get_org_unit(claims["tenant_id"], org_unit_id)
        return OrgUnitRead.model_validate(org_unit)
    except (NotFoundError, ConflictError, AuthError) as exc:
        _handle_identity_error(exc)
        raise


@router.patch(
    "/org-units/{org_unit_id}",
    response_model=OrgUnitRead,
    dependencies=[Depends(require_perm(PERM_IDENTITY_WRITE))],
)
def update_org_unit(
    org_unit_id: str,
    payload: OrgUnitUpdate,
    claims: Claims,
    service: Service,
) -> OrgUnitRead:
    try:
        org_unit = service.update_org_unit(claims["tenant_id"], org_unit_id, payload)
        return OrgUnitRead.model_validate(org_unit)
    except (NotFoundError, ConflictError, AuthError) as exc:
        _handle_identity_error(exc)
        raise


@router.delete(
    "/org-units/{org_unit_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_perm(PERM_IDENTITY_WRITE))],
)
def delete_org_unit(org_unit_id: str, claims: Claims, service: Service) -> Response:
    try:
        service.delete_org_unit(claims["tenant_id"], org_unit_id)
    except (NotFoundError, ConflictError, AuthError) as exc:
        _handle_identity_error(exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/users/{user_id}/org-units/{org_unit_id}",
    response_model=UserOrgMembershipLinkRead,
    dependencies=[Depends(require_perm(PERM_IDENTITY_WRITE))],
)
def bind_user_org_unit(
    user_id: str,
    org_unit_id: str,
    claims: Claims,
    service: Service,
    payload: UserOrgMembershipBindRequest | None = None,
) -> UserOrgMembershipLinkRead:
    body = payload or UserOrgMembershipBindRequest()
    try:
        link = service.bind_user_org_unit(
            claims["tenant_id"],
            user_id,
            org_unit_id,
            is_primary=body.is_primary,
        )
        return UserOrgMembershipLinkRead.model_validate(link)
    except (NotFoundError, ConflictError, AuthError) as exc:
        _handle_identity_error(exc)
        raise


@router.delete(
    "/users/{user_id}/org-units/{org_unit_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_perm(PERM_IDENTITY_WRITE))],
)
def unbind_user_org_unit(user_id: str, org_unit_id: str, claims: Claims, service: Service) -> Response:
    try:
        service.unbind_user_org_unit(claims["tenant_id"], user_id, org_unit_id)
    except (NotFoundError, ConflictError, AuthError) as exc:
        _handle_identity_error(exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/users/{user_id}/org-units",
    response_model=list[UserOrgMembershipLinkRead],
    dependencies=[Depends(require_perm(PERM_IDENTITY_READ))],
)
def list_user_org_units(user_id: str, claims: Claims, service: Service) -> list[UserOrgMembershipLinkRead]:
    try:
        links = service.list_user_org_units(claims["tenant_id"], user_id)
        return [UserOrgMembershipLinkRead.model_validate(item) for item in links]
    except (NotFoundError, ConflictError, AuthError) as exc:
        _handle_identity_error(exc)
        raise


@router.get(
    "/users/{user_id}/data-policy",
    response_model=DataAccessPolicyRead,
    dependencies=[Depends(require_perm(PERM_IDENTITY_READ))],
)
def get_user_data_policy(
    user_id: str,
    claims: Claims,
    service: Service,
    request: Request,
) -> DataAccessPolicyRead:
    set_audit_context(
        request,
        action="identity.data_policy.get",
        detail={"what": {"target": {"user_id": user_id}}},
    )
    try:
        policy = service.get_user_data_policy(claims["tenant_id"], user_id)
        set_audit_context(request, detail={"what": {"policy": _policy_snapshot(policy)}})
        return DataAccessPolicyRead.model_validate(policy)
    except (NotFoundError, ConflictError, AuthError) as exc:
        if isinstance(exc, NotFoundError):
            deny_reason = "cross_tenant_boundary" if service.user_exists_any_tenant(user_id) else "resource_not_found"
            _set_scope_deny_audit(
                request,
                action="identity.data_policy.get",
                reason=deny_reason,
                target={"user_id": user_id},
            )
        _handle_identity_error(exc)
        raise


@router.put(
    "/users/{user_id}/data-policy",
    response_model=DataAccessPolicyRead,
    dependencies=[Depends(require_perm(PERM_IDENTITY_WRITE))],
)
def upsert_user_data_policy(
    user_id: str,
    payload: DataAccessPolicyUpdate,
    claims: Claims,
    service: Service,
    request: Request,
) -> DataAccessPolicyRead:
    set_audit_context(
        request,
        action="identity.data_policy.upsert",
        detail={
            "what": {
                "target": {"user_id": user_id},
                "requested_policy": _policy_snapshot(payload),
            }
        },
    )
    try:
        before_policy = service.get_user_data_policy(claims["tenant_id"], user_id)
    except (NotFoundError, ConflictError, AuthError) as exc:
        if isinstance(exc, NotFoundError):
            deny_reason = "cross_tenant_boundary" if service.user_exists_any_tenant(user_id) else "resource_not_found"
            _set_scope_deny_audit(
                request,
                action="identity.data_policy.upsert",
                reason=deny_reason,
                target={"user_id": user_id},
            )
        _handle_identity_error(exc)
        raise
    try:
        policy = service.upsert_user_data_policy(claims["tenant_id"], user_id, payload)
        before = _policy_snapshot(before_policy)
        after = _policy_snapshot(policy)
        changed_fields = sorted([key for key, value in after.items() if before.get(key) != value])
        set_audit_context(
            request,
            detail={
                "what": {
                    "policy_before": before,
                    "policy_after": after,
                    "changed_fields": changed_fields,
                }
            },
        )
        return DataAccessPolicyRead.model_validate(policy)
    except (NotFoundError, ConflictError, AuthError) as exc:
        if isinstance(exc, NotFoundError):
            deny_reason = "cross_tenant_boundary" if service.user_exists_any_tenant(user_id) else "resource_not_found"
            _set_scope_deny_audit(
                request,
                action="identity.data_policy.upsert",
                reason=deny_reason,
                target={"user_id": user_id},
            )
        _handle_identity_error(exc)
        raise


@router.post(
    "/permissions",
    response_model=PermissionRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_perm(PERM_IDENTITY_WRITE))],
)
def create_permission(payload: PermissionCreate, service: Service) -> PermissionRead:
    try:
        permission = service.create_permission(payload)
        return PermissionRead.model_validate(permission)
    except (NotFoundError, ConflictError, AuthError) as exc:
        _handle_identity_error(exc)
        raise


@router.get(
    "/permissions",
    response_model=list[PermissionRead],
    dependencies=[Depends(require_perm(PERM_IDENTITY_READ))],
)
def list_permissions(service: Service) -> list[PermissionRead]:
    permissions = service.list_permissions()
    return [PermissionRead.model_validate(item) for item in permissions]


@router.get(
    "/permissions/{permission_id}",
    response_model=PermissionRead,
    dependencies=[Depends(require_perm(PERM_IDENTITY_READ))],
)
def get_permission(permission_id: str, service: Service) -> PermissionRead:
    try:
        permission = service.get_permission(permission_id)
        return PermissionRead.model_validate(permission)
    except (NotFoundError, ConflictError, AuthError) as exc:
        _handle_identity_error(exc)
        raise


@router.patch(
    "/permissions/{permission_id}",
    response_model=PermissionRead,
    dependencies=[Depends(require_perm(PERM_IDENTITY_WRITE))],
)
def update_permission(permission_id: str, payload: PermissionUpdate, service: Service) -> PermissionRead:
    try:
        permission = service.update_permission(permission_id, payload)
        return PermissionRead.model_validate(permission)
    except (NotFoundError, ConflictError, AuthError) as exc:
        _handle_identity_error(exc)
        raise


@router.delete(
    "/permissions/{permission_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_perm(PERM_IDENTITY_WRITE))],
)
def delete_permission(permission_id: str, service: Service) -> Response:
    try:
        service.delete_permission(permission_id)
    except (NotFoundError, ConflictError, AuthError) as exc:
        _handle_identity_error(exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/users/{user_id}/roles:batch-bind",
    response_model=UserRoleBatchBindRead,
    dependencies=[Depends(require_perm(PERM_IDENTITY_WRITE))],
)
def bind_user_roles_batch(
    user_id: str,
    payload: UserRoleBatchBindRequest,
    claims: Claims,
    service: Service,
    request: Request,
) -> UserRoleBatchBindRead:
    set_audit_context(
        request,
        action="identity.user_role.batch_bind",
        detail={
            "what": {
                "target": {"user_id": user_id},
                "requested_role_ids": payload.role_ids,
            }
        },
    )
    try:
        result = service.bind_user_roles_batch(claims["tenant_id"], user_id, payload.role_ids)
    except (NotFoundError, ConflictError, AuthError) as exc:
        if isinstance(exc, NotFoundError):
            deny_reason = "cross_tenant_boundary" if service.user_exists_any_tenant(user_id) else "resource_not_found"
            _set_scope_deny_audit(
                request,
                action="identity.user_role.batch_bind",
                reason=deny_reason,
                target={"user_id": user_id},
            )
        _handle_identity_error(exc)
        raise

    denied_role_ids = [item["role_id"] for item in result["results"] if item["status"] == "cross_tenant_denied"]
    missing_role_ids = [item["role_id"] for item in result["results"] if item["status"] == "not_found"]
    if denied_role_ids:
        outcome = "partial_denied"
        reason = "cross_tenant_boundary"
    elif missing_role_ids:
        outcome = "partial_missing"
        reason = "role_not_found"
    else:
        outcome = "success"
        reason = "ok"
    set_audit_context(
        request,
        detail={
            "what": {
                "batch_result": {
                    "requested_count": result["requested_count"],
                    "bound_count": result["bound_count"],
                    "already_bound_count": result["already_bound_count"],
                    "denied_count": result["denied_count"],
                    "missing_count": result["missing_count"],
                },
                "denied_role_ids": denied_role_ids,
                "missing_role_ids": missing_role_ids,
            },
            "result": {
                "outcome": outcome,
                "reason": reason,
            },
        },
    )
    return UserRoleBatchBindRead.model_validate(result)


@router.post(
    "/users/{user_id}/roles/{role_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_perm(PERM_IDENTITY_WRITE))],
)
def bind_user_role(
    user_id: str,
    role_id: str,
    claims: Claims,
    service: Service,
    request: Request,
) -> Response:
    set_audit_context(
        request,
        action="identity.user_role.bind",
        detail={"what": {"target": {"user_id": user_id, "role_id": role_id}}},
    )
    try:
        service.bind_user_role(claims["tenant_id"], user_id, role_id)
    except (NotFoundError, ConflictError, AuthError) as exc:
        if isinstance(exc, NotFoundError):
            is_scope_denied = service.user_exists_any_tenant(user_id) and service.role_exists_any_tenant(role_id)
            deny_reason = "cross_tenant_boundary" if is_scope_denied else "resource_not_found"
            _set_scope_deny_audit(
                request,
                action="identity.user_role.bind",
                reason=deny_reason,
                target={"user_id": user_id, "role_id": role_id},
            )
        _handle_identity_error(exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/users/{user_id}/roles/{role_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_perm(PERM_IDENTITY_WRITE))],
)
def unbind_user_role(
    user_id: str,
    role_id: str,
    claims: Claims,
    service: Service,
    request: Request,
) -> Response:
    set_audit_context(
        request,
        action="identity.user_role.unbind",
        detail={"what": {"target": {"user_id": user_id, "role_id": role_id}}},
    )
    try:
        service.unbind_user_role(claims["tenant_id"], user_id, role_id)
    except (NotFoundError, ConflictError, AuthError) as exc:
        if isinstance(exc, NotFoundError):
            is_scope_denied = service.user_exists_any_tenant(user_id) and service.role_exists_any_tenant(role_id)
            deny_reason = "cross_tenant_boundary" if is_scope_denied else "resource_not_found"
            _set_scope_deny_audit(
                request,
                action="identity.user_role.unbind",
                reason=deny_reason,
                target={"user_id": user_id, "role_id": role_id},
            )
        _handle_identity_error(exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/roles/{role_id}/permissions/{permission_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_perm(PERM_IDENTITY_WRITE))],
)
def bind_role_permission(
    role_id: str,
    permission_id: str,
    claims: Claims,
    service: Service,
) -> Response:
    try:
        service.bind_role_permission(claims["tenant_id"], role_id, permission_id)
    except (NotFoundError, ConflictError, AuthError) as exc:
        _handle_identity_error(exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/roles/{role_id}/permissions/{permission_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_perm(PERM_IDENTITY_WRITE))],
)
def unbind_role_permission(
    role_id: str,
    permission_id: str,
    claims: Claims,
    service: Service,
) -> Response:
    try:
        service.unbind_role_permission(claims["tenant_id"], role_id, permission_id)
    except (NotFoundError, ConflictError, AuthError) as exc:
        _handle_identity_error(exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
