from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.api.deps import get_current_claims, require_perm
from app.domain.permissions import PERM_WILDCARD
from app.services.tenant_export_service import NotFoundError, TenantExportService

router = APIRouter()


def get_tenant_export_service() -> TenantExportService:
    return TenantExportService()


Claims = Annotated[dict[str, Any], Depends(get_current_claims)]
Service = Annotated[TenantExportService, Depends(get_tenant_export_service)]


class TenantExportCreateResponse(BaseModel):
    export_id: str
    status: str
    manifest_path: str
    zip_path: str | None = None


class TenantExportStatusResponse(BaseModel):
    export_id: str
    tenant_id: str
    status: str
    export_version: str
    created_at: str
    tables: list[dict[str, Any]]
    global_tables_skipped: list[str]
    zip_file: str | None = None


def _enforce_tenant_match(claims: dict[str, Any], tenant_id: str) -> None:
    if claims.get("tenant_id") != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="tenant not found")


@router.post(
    "/tenants/{tenant_id}/export",
    response_model=TenantExportCreateResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_perm(PERM_WILDCARD))],
)
def create_tenant_export(
    tenant_id: str,
    claims: Claims,
    service: Service,
    include_zip: Annotated[bool, Query()] = False,
) -> TenantExportCreateResponse:
    _enforce_tenant_match(claims, tenant_id)
    try:
        return TenantExportCreateResponse.model_validate(
            service.create_export(tenant_id, include_zip=include_zip)
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get(
    "/tenants/{tenant_id}/export/{export_id}",
    response_model=TenantExportStatusResponse,
    dependencies=[Depends(require_perm(PERM_WILDCARD))],
)
def get_tenant_export_status(
    tenant_id: str,
    export_id: str,
    claims: Claims,
    service: Service,
) -> TenantExportStatusResponse:
    _enforce_tenant_match(claims, tenant_id)
    try:
        manifest = service.get_export_manifest(tenant_id, export_id)
        return TenantExportStatusResponse.model_validate(manifest)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get(
    "/tenants/{tenant_id}/export/{export_id}/download",
    dependencies=[Depends(require_perm(PERM_WILDCARD))],
)
def download_tenant_export(
    tenant_id: str,
    export_id: str,
    claims: Claims,
    service: Service,
) -> FileResponse:
    _enforce_tenant_match(claims, tenant_id)
    try:
        zip_path = service.get_export_zip_path(tenant_id, export_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    path = Path(zip_path)
    return FileResponse(path=path, media_type="application/zip", filename=path.name)
