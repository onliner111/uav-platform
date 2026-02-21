from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_claims, require_perm
from app.domain.models import (
    IncidentCreate,
    IncidentCreateTaskRead,
    IncidentCreateTaskRequest,
    IncidentRead,
)
from app.domain.permissions import PERM_INCIDENT_READ, PERM_INCIDENT_WRITE
from app.services.incident_service import ConflictError, IncidentService, NotFoundError

router = APIRouter()


def get_incident_service() -> IncidentService:
    return IncidentService()


Claims = Annotated[dict[str, Any], Depends(get_current_claims)]
Service = Annotated[IncidentService, Depends(get_incident_service)]


def _handle_incident_error(exc: Exception) -> None:
    if isinstance(exc, NotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if isinstance(exc, ConflictError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    raise exc


@router.post(
    "",
    response_model=IncidentRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_perm(PERM_INCIDENT_WRITE))],
)
def create_incident(payload: IncidentCreate, claims: Claims, service: Service) -> IncidentRead:
    row = service.create_incident(claims["tenant_id"], payload)
    return IncidentRead.model_validate(row)


@router.get(
    "",
    response_model=list[IncidentRead],
    dependencies=[Depends(require_perm(PERM_INCIDENT_READ))],
)
def list_incidents(claims: Claims, service: Service) -> list[IncidentRead]:
    rows = service.list_incidents(claims["tenant_id"])
    return [IncidentRead.model_validate(item) for item in rows]


@router.post(
    "/{incident_id}/create-task",
    response_model=IncidentCreateTaskRead,
    dependencies=[Depends(require_perm(PERM_INCIDENT_WRITE))],
)
def create_task(
    incident_id: str,
    payload: IncidentCreateTaskRequest,
    claims: Claims,
    service: Service,
) -> IncidentCreateTaskRead:
    try:
        return service.create_task_for_incident(claims["tenant_id"], claims["sub"], incident_id, payload)
    except (NotFoundError, ConflictError) as exc:
        _handle_incident_error(exc)
        raise
