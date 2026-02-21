from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse

from app.api.deps import get_current_claims, require_perm
from app.domain.models import (
    InspectionExportRead,
    InspectionObservationCreate,
    InspectionObservationRead,
    InspectionTaskCreate,
    InspectionTaskRead,
    InspectionTaskStatus,
    InspectionTemplateCreate,
    InspectionTemplateItemCreate,
    InspectionTemplateItemRead,
    InspectionTemplateRead,
)
from app.domain.permissions import PERM_INSPECTION_READ, PERM_INSPECTION_WRITE
from app.services.inspection_service import ConflictError, InspectionService, NotFoundError

router = APIRouter()


def get_inspection_service() -> InspectionService:
    return InspectionService()


Claims = Annotated[dict[str, Any], Depends(get_current_claims)]
Service = Annotated[InspectionService, Depends(get_inspection_service)]


def _handle_inspection_error(exc: Exception) -> None:
    if isinstance(exc, NotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if isinstance(exc, ConflictError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    raise exc


@router.get(
    "/templates",
    response_model=list[InspectionTemplateRead],
    dependencies=[Depends(require_perm(PERM_INSPECTION_READ))],
)
def list_templates(claims: Claims, service: Service) -> list[InspectionTemplateRead]:
    rows = service.list_templates(claims["tenant_id"])
    return [InspectionTemplateRead.model_validate(item) for item in rows]


@router.post(
    "/templates",
    response_model=InspectionTemplateRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_perm(PERM_INSPECTION_WRITE))],
)
def create_template(payload: InspectionTemplateCreate, claims: Claims, service: Service) -> InspectionTemplateRead:
    row = service.create_template(claims["tenant_id"], payload)
    return InspectionTemplateRead.model_validate(row)


@router.get(
    "/templates/{template_id}",
    response_model=InspectionTemplateRead,
    dependencies=[Depends(require_perm(PERM_INSPECTION_READ))],
)
def get_template(template_id: str, claims: Claims, service: Service) -> InspectionTemplateRead:
    try:
        row = service.get_template(claims["tenant_id"], template_id)
        return InspectionTemplateRead.model_validate(row)
    except (NotFoundError, ConflictError) as exc:
        _handle_inspection_error(exc)
        raise


@router.post(
    "/templates/{template_id}/items",
    response_model=InspectionTemplateItemRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_perm(PERM_INSPECTION_WRITE))],
)
def create_template_item(
    template_id: str,
    payload: InspectionTemplateItemCreate,
    claims: Claims,
    service: Service,
) -> InspectionTemplateItemRead:
    try:
        row = service.create_template_item(claims["tenant_id"], template_id, payload)
        return InspectionTemplateItemRead.model_validate(row)
    except (NotFoundError, ConflictError) as exc:
        _handle_inspection_error(exc)
        raise


@router.get(
    "/templates/{template_id}/items",
    response_model=list[InspectionTemplateItemRead],
    dependencies=[Depends(require_perm(PERM_INSPECTION_READ))],
)
def list_template_items(template_id: str, claims: Claims, service: Service) -> list[InspectionTemplateItemRead]:
    try:
        rows = service.list_template_items(claims["tenant_id"], template_id)
        return [InspectionTemplateItemRead.model_validate(item) for item in rows]
    except (NotFoundError, ConflictError) as exc:
        _handle_inspection_error(exc)
        raise


@router.post(
    "/tasks",
    response_model=InspectionTaskRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_perm(PERM_INSPECTION_WRITE))],
)
def create_task(payload: InspectionTaskCreate, claims: Claims, service: Service) -> InspectionTaskRead:
    try:
        row = service.create_task(claims["tenant_id"], payload)
        return InspectionTaskRead.model_validate(row)
    except (NotFoundError, ConflictError) as exc:
        _handle_inspection_error(exc)
        raise


@router.get(
    "/tasks",
    response_model=list[InspectionTaskRead],
    dependencies=[Depends(require_perm(PERM_INSPECTION_READ))],
)
def list_tasks(
    claims: Claims,
    service: Service,
    task_status: Annotated[InspectionTaskStatus | None, Query(alias="status")] = None,
) -> list[InspectionTaskRead]:
    rows = service.list_tasks(claims["tenant_id"], task_status)
    return [InspectionTaskRead.model_validate(item) for item in rows]


@router.get(
    "/tasks/{task_id}",
    response_model=InspectionTaskRead,
    dependencies=[Depends(require_perm(PERM_INSPECTION_READ))],
)
def get_task(task_id: str, claims: Claims, service: Service) -> InspectionTaskRead:
    try:
        row = service.get_task(claims["tenant_id"], task_id)
        return InspectionTaskRead.model_validate(row)
    except (NotFoundError, ConflictError) as exc:
        _handle_inspection_error(exc)
        raise


@router.post(
    "/tasks/{task_id}/observations",
    response_model=InspectionObservationRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_perm(PERM_INSPECTION_WRITE))],
)
def create_observation(
    task_id: str,
    payload: InspectionObservationCreate,
    claims: Claims,
    service: Service,
) -> InspectionObservationRead:
    try:
        row = service.create_observation(claims["tenant_id"], task_id, payload)
        return InspectionObservationRead.model_validate(row)
    except (NotFoundError, ConflictError) as exc:
        _handle_inspection_error(exc)
        raise


@router.get(
    "/tasks/{task_id}/observations",
    response_model=list[InspectionObservationRead],
    dependencies=[Depends(require_perm(PERM_INSPECTION_READ))],
)
def list_observations(task_id: str, claims: Claims, service: Service) -> list[InspectionObservationRead]:
    try:
        rows = service.list_observations(claims["tenant_id"], task_id)
        return [InspectionObservationRead.model_validate(item) for item in rows]
    except (NotFoundError, ConflictError) as exc:
        _handle_inspection_error(exc)
        raise


@router.post(
    "/tasks/{task_id}/export",
    response_model=InspectionExportRead,
    dependencies=[Depends(require_perm(PERM_INSPECTION_WRITE))],
)
def export_task(
    task_id: str,
    claims: Claims,
    service: Service,
    export_format: Annotated[str, Query(alias="format")] = "html",
) -> InspectionExportRead:
    try:
        row = service.create_export(claims["tenant_id"], task_id, export_format)
        return InspectionExportRead.model_validate(row)
    except (NotFoundError, ConflictError) as exc:
        _handle_inspection_error(exc)
        raise


@router.get(
    "/exports/{export_id}",
    dependencies=[Depends(require_perm(PERM_INSPECTION_READ))],
)
def get_export(export_id: str, claims: Claims, service: Service) -> FileResponse:
    try:
        export = service.get_export(claims["tenant_id"], export_id)
    except (NotFoundError, ConflictError) as exc:
        _handle_inspection_error(exc)
        raise
    path = Path(export.file_path)
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="export file not found")
    return FileResponse(path, media_type="text/html", filename=path.name)
