from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.deps import get_current_claims, require_perm
from app.domain.models import (
    MaintenanceWorkOrderCloseRequest,
    MaintenanceWorkOrderCreate,
    MaintenanceWorkOrderHistoryRead,
    MaintenanceWorkOrderRead,
    MaintenanceWorkOrderStatus,
    MaintenanceWorkOrderTransitionRequest,
)
from app.domain.permissions import PERM_REGISTRY_READ, PERM_REGISTRY_WRITE
from app.infra.audit import set_audit_context
from app.services.asset_maintenance_service import (
    AssetMaintenanceService,
    ConflictError,
    NotFoundError,
)

router = APIRouter()


def get_asset_maintenance_service() -> AssetMaintenanceService:
    return AssetMaintenanceService()


Claims = Annotated[dict[str, Any], Depends(get_current_claims)]
Service = Annotated[AssetMaintenanceService, Depends(get_asset_maintenance_service)]


def _handle_error(exc: Exception) -> None:
    if isinstance(exc, NotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if isinstance(exc, ConflictError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    raise exc


@router.post(
    "/workorders",
    response_model=MaintenanceWorkOrderRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_perm(PERM_REGISTRY_WRITE))],
)
def create_workorder(
    payload: MaintenanceWorkOrderCreate,
    request: Request,
    claims: Claims,
    service: Service,
) -> MaintenanceWorkOrderRead:
    set_audit_context(
        request,
        action="asset.maintenance_workorder.create",
        detail={"what": {"asset_id": payload.asset_id}},
    )
    try:
        row = service.create_workorder(claims["tenant_id"], claims["sub"], payload)
        return MaintenanceWorkOrderRead.model_validate(row)
    except (NotFoundError, ConflictError) as exc:
        _handle_error(exc)
        raise


@router.get(
    "/workorders",
    response_model=list[MaintenanceWorkOrderRead],
    dependencies=[Depends(require_perm(PERM_REGISTRY_READ))],
)
def list_workorders(
    claims: Claims,
    service: Service,
    asset_id: str | None = None,
    status: MaintenanceWorkOrderStatus | None = None,
) -> list[MaintenanceWorkOrderRead]:
    rows = service.list_workorders(claims["tenant_id"], asset_id=asset_id, status=status)
    return [MaintenanceWorkOrderRead.model_validate(item) for item in rows]


@router.get(
    "/workorders/{workorder_id}",
    response_model=MaintenanceWorkOrderRead,
    dependencies=[Depends(require_perm(PERM_REGISTRY_READ))],
)
def get_workorder(workorder_id: str, claims: Claims, service: Service) -> MaintenanceWorkOrderRead:
    try:
        row = service.get_workorder(claims["tenant_id"], workorder_id)
        return MaintenanceWorkOrderRead.model_validate(row)
    except (NotFoundError, ConflictError) as exc:
        _handle_error(exc)
        raise


@router.post(
    "/workorders/{workorder_id}/transition",
    response_model=MaintenanceWorkOrderRead,
    dependencies=[Depends(require_perm(PERM_REGISTRY_WRITE))],
)
def transition_workorder(
    workorder_id: str,
    payload: MaintenanceWorkOrderTransitionRequest,
    request: Request,
    claims: Claims,
    service: Service,
) -> MaintenanceWorkOrderRead:
    set_audit_context(
        request,
        action="asset.maintenance_workorder.transition",
        detail={"what": {"target_status": payload.status}},
    )
    try:
        row = service.transition_workorder(claims["tenant_id"], workorder_id, claims["sub"], payload)
        return MaintenanceWorkOrderRead.model_validate(row)
    except (NotFoundError, ConflictError) as exc:
        _handle_error(exc)
        raise


@router.post(
    "/workorders/{workorder_id}/close",
    response_model=MaintenanceWorkOrderRead,
    dependencies=[Depends(require_perm(PERM_REGISTRY_WRITE))],
)
def close_workorder(
    workorder_id: str,
    payload: MaintenanceWorkOrderCloseRequest,
    request: Request,
    claims: Claims,
    service: Service,
) -> MaintenanceWorkOrderRead:
    set_audit_context(
        request,
        action="asset.maintenance_workorder.close",
        detail={"what": {"workorder_id": workorder_id}},
    )
    try:
        row = service.close_workorder(claims["tenant_id"], workorder_id, claims["sub"], payload)
        return MaintenanceWorkOrderRead.model_validate(row)
    except (NotFoundError, ConflictError) as exc:
        _handle_error(exc)
        raise


@router.get(
    "/workorders/{workorder_id}/history",
    response_model=list[MaintenanceWorkOrderHistoryRead],
    dependencies=[Depends(require_perm(PERM_REGISTRY_READ))],
)
def list_workorder_history(
    workorder_id: str,
    request: Request,
    claims: Claims,
    service: Service,
) -> list[MaintenanceWorkOrderHistoryRead]:
    set_audit_context(
        request,
        action="asset.maintenance_workorder.history.list",
        detail={"what": {"workorder_id": workorder_id}},
    )
    try:
        rows = service.list_history(claims["tenant_id"], workorder_id)
        return [MaintenanceWorkOrderHistoryRead.model_validate(item) for item in rows]
    except (NotFoundError, ConflictError) as exc:
        _handle_error(exc)
        raise
