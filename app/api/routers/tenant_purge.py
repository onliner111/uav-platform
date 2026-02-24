from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.api.deps import get_current_claims, require_perm
from app.domain.permissions import PERM_WILDCARD
from app.services.tenant_purge_service import (
    TENANT_PURGE_CONFIRM_PHRASE,
    ConflictError,
    NotFoundError,
    TenantPurgeService,
    ValidationError,
)

router = APIRouter()


def get_tenant_purge_service() -> TenantPurgeService:
    return TenantPurgeService()


Claims = Annotated[dict[str, Any], Depends(get_current_claims)]
Service = Annotated[TenantPurgeService, Depends(get_tenant_purge_service)]


class TenantPurgeDryRunResponse(BaseModel):
    dry_run_id: str
    tenant_id: str
    status: str
    purge_version: str
    created_at: str
    plan: list[str]
    counts: dict[str, int]
    estimated_rows: int
    safety: dict[str, Any]
    confirm_token: str
    dry_run_path: str


class TenantPurgeExecuteRequest(BaseModel):
    dry_run_id: str
    confirm_token: str | None = None
    confirm_phrase: str | None = None
    mode: str = "hard"


class TenantPurgeExecuteResponse(BaseModel):
    purge_id: str
    tenant_id: str
    dry_run_id: str
    status: str
    report_path: str
    deleted_rows: int
    post_delete_counts: dict[str, int]


class TenantPurgeStatusResponse(BaseModel):
    purge_id: str
    dry_run_id: str
    tenant_id: str
    status: str
    purge_version: str
    executed_at: str
    mode: str
    confirm_method: str
    plan: list[str]
    dry_run_counts: dict[str, int]
    pre_delete_counts: dict[str, int]
    deleted_counts: dict[str, int]
    post_delete_counts: dict[str, int]
    deleted_rows: int
    dry_run_drift_detected: bool


def _enforce_tenant_match(claims: dict[str, Any], tenant_id: str) -> None:
    if claims.get("tenant_id") != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="tenant not found")


@router.post(
    "/tenants/{tenant_id}/purge:dry_run",
    response_model=TenantPurgeDryRunResponse,
    dependencies=[Depends(require_perm(PERM_WILDCARD))],
)
def create_tenant_purge_dry_run(
    tenant_id: str,
    claims: Claims,
    service: Service,
) -> TenantPurgeDryRunResponse:
    _enforce_tenant_match(claims, tenant_id)
    try:
        payload = service.create_dry_run(tenant_id)
        return TenantPurgeDryRunResponse.model_validate(payload)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/tenants/{tenant_id}/purge",
    response_model=TenantPurgeExecuteResponse,
    dependencies=[Depends(require_perm(PERM_WILDCARD))],
)
def execute_tenant_purge(
    tenant_id: str,
    payload: TenantPurgeExecuteRequest,
    claims: Claims,
    service: Service,
) -> TenantPurgeExecuteResponse:
    _enforce_tenant_match(claims, tenant_id)
    try:
        result = service.execute_purge(
            tenant_id=tenant_id,
            dry_run_id=payload.dry_run_id,
            confirm_token=payload.confirm_token,
            confirm_phrase=payload.confirm_phrase,
            mode=payload.mode,
        )
        return TenantPurgeExecuteResponse.model_validate(result)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get(
    "/tenants/{tenant_id}/purge/{purge_id}",
    response_model=TenantPurgeStatusResponse,
    dependencies=[Depends(require_perm(PERM_WILDCARD))],
)
def get_tenant_purge_status(
    tenant_id: str,
    purge_id: str,
    claims: Claims,
    service: Service,
) -> TenantPurgeStatusResponse:
    _enforce_tenant_match(claims, tenant_id)
    try:
        report = service.get_purge_report(tenant_id, purge_id)
        return TenantPurgeStatusResponse.model_validate(report)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


__all__ = ["TENANT_PURGE_CONFIRM_PHRASE"]
