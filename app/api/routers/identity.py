from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.api.deps import get_current_claims, require_perm
from app.domain.models import (
    BootstrapAdminRequest,
    DevLoginRequest,
    PermissionCreate,
    PermissionRead,
    PermissionUpdate,
    RoleCreate,
    RoleRead,
    RoleUpdate,
    TenantCreate,
    TenantRead,
    TenantUpdate,
    TokenResponse,
    UserCreate,
    UserRead,
    UserUpdate,
)
from app.domain.permissions import PERM_IDENTITY_READ, PERM_IDENTITY_WRITE
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
    "/users/{user_id}/roles/{role_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_perm(PERM_IDENTITY_WRITE))],
)
def bind_user_role(user_id: str, role_id: str, claims: Claims, service: Service) -> Response:
    try:
        service.bind_user_role(claims["tenant_id"], user_id, role_id)
    except (NotFoundError, ConflictError, AuthError) as exc:
        _handle_identity_error(exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/users/{user_id}/roles/{role_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_perm(PERM_IDENTITY_WRITE))],
)
def unbind_user_role(user_id: str, role_id: str, claims: Claims, service: Service) -> Response:
    try:
        service.unbind_user_role(claims["tenant_id"], user_id, role_id)
    except (NotFoundError, ConflictError, AuthError) as exc:
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
