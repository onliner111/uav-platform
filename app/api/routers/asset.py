from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_claims, require_perm
from app.domain.models import (
    AssetAvailabilityStatus,
    AssetAvailabilityUpdateRequest,
    AssetBindRequest,
    AssetCreate,
    AssetHealthStatus,
    AssetHealthUpdateRequest,
    AssetLifecycleStatus,
    AssetPoolRegionSummaryRead,
    AssetRead,
    AssetRetireRequest,
    AssetType,
)
from app.domain.permissions import PERM_REGISTRY_READ, PERM_REGISTRY_WRITE
from app.services.asset_service import AssetService, ConflictError, NotFoundError

router = APIRouter()


def get_asset_service() -> AssetService:
    return AssetService()


Claims = Annotated[dict[str, Any], Depends(get_current_claims)]
Service = Annotated[AssetService, Depends(get_asset_service)]


def _handle_asset_error(exc: Exception) -> None:
    if isinstance(exc, NotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if isinstance(exc, ConflictError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    raise exc


@router.post(
    "",
    response_model=AssetRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_perm(PERM_REGISTRY_WRITE))],
)
def create_asset(payload: AssetCreate, claims: Claims, service: Service) -> AssetRead:
    try:
        asset = service.create_asset(claims["tenant_id"], payload)
        return AssetRead.model_validate(asset)
    except (NotFoundError, ConflictError) as exc:
        _handle_asset_error(exc)
        raise


@router.get(
    "",
    response_model=list[AssetRead],
    dependencies=[Depends(require_perm(PERM_REGISTRY_READ))],
)
def list_assets(
    claims: Claims,
    service: Service,
    asset_type: AssetType | None = None,
    lifecycle_status: AssetLifecycleStatus | None = None,
    availability_status: AssetAvailabilityStatus | None = None,
    health_status: AssetHealthStatus | None = None,
    region_code: str | None = None,
) -> list[AssetRead]:
    rows = service.list_assets(
        claims["tenant_id"],
        asset_type=asset_type,
        lifecycle_status=lifecycle_status,
        availability_status=availability_status,
        health_status=health_status,
        region_code=region_code,
        viewer_user_id=claims["sub"],
    )
    return [AssetRead.model_validate(item) for item in rows]


@router.get(
    "/pool",
    response_model=list[AssetRead],
    dependencies=[Depends(require_perm(PERM_REGISTRY_READ))],
)
def list_resource_pool(
    claims: Claims,
    service: Service,
    asset_type: AssetType | None = None,
    availability_status: AssetAvailabilityStatus = AssetAvailabilityStatus.AVAILABLE,
    health_status: AssetHealthStatus | None = None,
    region_code: str | None = None,
    min_health_score: int | None = None,
) -> list[AssetRead]:
    rows = service.list_resource_pool(
        claims["tenant_id"],
        asset_type=asset_type,
        availability_status=availability_status,
        health_status=health_status,
        region_code=region_code,
        min_health_score=min_health_score,
        viewer_user_id=claims["sub"],
    )
    return [AssetRead.model_validate(item) for item in rows]


@router.get(
    "/pool/summary",
    response_model=list[AssetPoolRegionSummaryRead],
    dependencies=[Depends(require_perm(PERM_REGISTRY_READ))],
)
def summarize_resource_pool(
    claims: Claims,
    service: Service,
    asset_type: AssetType | None = None,
    health_status: AssetHealthStatus | None = None,
    region_code: str | None = None,
    min_health_score: int | None = None,
) -> list[AssetPoolRegionSummaryRead]:
    rows = service.summarize_resource_pool(
        claims["tenant_id"],
        asset_type=asset_type,
        health_status=health_status,
        region_code=region_code,
        min_health_score=min_health_score,
        viewer_user_id=claims["sub"],
    )
    return [AssetPoolRegionSummaryRead.model_validate(item) for item in rows]


@router.get(
    "/{asset_id}",
    response_model=AssetRead,
    dependencies=[Depends(require_perm(PERM_REGISTRY_READ))],
)
def get_asset(asset_id: str, claims: Claims, service: Service) -> AssetRead:
    try:
        asset = service.get_asset(claims["tenant_id"], asset_id, viewer_user_id=claims["sub"])
        return AssetRead.model_validate(asset)
    except (NotFoundError, ConflictError) as exc:
        _handle_asset_error(exc)
        raise


@router.post(
    "/{asset_id}/bind",
    response_model=AssetRead,
    dependencies=[Depends(require_perm(PERM_REGISTRY_WRITE))],
)
def bind_asset(asset_id: str, payload: AssetBindRequest, claims: Claims, service: Service) -> AssetRead:
    try:
        asset = service.bind_asset(claims["tenant_id"], asset_id, payload, viewer_user_id=claims["sub"])
        return AssetRead.model_validate(asset)
    except (NotFoundError, ConflictError) as exc:
        _handle_asset_error(exc)
        raise


@router.post(
    "/{asset_id}/availability",
    response_model=AssetRead,
    dependencies=[Depends(require_perm(PERM_REGISTRY_WRITE))],
)
def update_asset_availability(
    asset_id: str,
    payload: AssetAvailabilityUpdateRequest,
    claims: Claims,
    service: Service,
) -> AssetRead:
    try:
        asset = service.update_availability(claims["tenant_id"], asset_id, payload, viewer_user_id=claims["sub"])
        return AssetRead.model_validate(asset)
    except (NotFoundError, ConflictError) as exc:
        _handle_asset_error(exc)
        raise


@router.post(
    "/{asset_id}/health",
    response_model=AssetRead,
    dependencies=[Depends(require_perm(PERM_REGISTRY_WRITE))],
)
def update_asset_health(
    asset_id: str,
    payload: AssetHealthUpdateRequest,
    claims: Claims,
    service: Service,
) -> AssetRead:
    try:
        asset = service.update_health(claims["tenant_id"], asset_id, payload, viewer_user_id=claims["sub"])
        return AssetRead.model_validate(asset)
    except (NotFoundError, ConflictError) as exc:
        _handle_asset_error(exc)
        raise


@router.post(
    "/{asset_id}/retire",
    response_model=AssetRead,
    dependencies=[Depends(require_perm(PERM_REGISTRY_WRITE))],
)
def retire_asset(asset_id: str, payload: AssetRetireRequest, claims: Claims, service: Service) -> AssetRead:
    try:
        asset = service.retire_asset(claims["tenant_id"], asset_id, payload, viewer_user_id=claims["sub"])
        return AssetRead.model_validate(asset)
    except (NotFoundError, ConflictError) as exc:
        _handle_asset_error(exc)
        raise
