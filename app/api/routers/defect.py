from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_current_claims, require_perm
from app.domain.models import (
    DefectActionRead,
    DefectAssignRequest,
    DefectCreateFromObservationRead,
    DefectDetailRead,
    DefectStatsRead,
    DefectStatus,
    DefectStatusRequest,
)
from app.domain.permissions import PERM_DEFECT_READ, PERM_DEFECT_WRITE
from app.services.defect_service import ConflictError, DefectService, NotFoundError

router = APIRouter()


def get_defect_service() -> DefectService:
    return DefectService()


Claims = Annotated[dict[str, Any], Depends(get_current_claims)]
Service = Annotated[DefectService, Depends(get_defect_service)]


def _handle_defect_error(exc: Exception) -> None:
    if isinstance(exc, NotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if isinstance(exc, ConflictError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    raise exc


@router.post(
    "/from-observation/{observation_id}",
    response_model=DefectCreateFromObservationRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_perm(PERM_DEFECT_WRITE))],
)
def create_from_observation(
    observation_id: str,
    claims: Claims,
    service: Service,
) -> DefectCreateFromObservationRead:
    try:
        row = service.create_from_observation(claims["tenant_id"], observation_id, viewer_user_id=claims["sub"])
        return DefectCreateFromObservationRead.model_validate(row)
    except (NotFoundError, ConflictError) as exc:
        _handle_defect_error(exc)
        raise


@router.get(
    "",
    response_model=list[DefectCreateFromObservationRead],
    dependencies=[Depends(require_perm(PERM_DEFECT_READ))],
)
def list_defects(
    claims: Claims,
    service: Service,
    defect_status: Annotated[DefectStatus | None, Query(alias="status")] = None,
    assigned_to: str | None = None,
) -> list[DefectCreateFromObservationRead]:
    rows = service.list_defects(
        claims["tenant_id"],
        status=defect_status,
        assigned_to=assigned_to,
        viewer_user_id=claims["sub"],
    )
    return [DefectCreateFromObservationRead.model_validate(item) for item in rows]


@router.get(
    "/stats",
    response_model=DefectStatsRead,
    dependencies=[Depends(require_perm(PERM_DEFECT_READ))],
)
def defect_stats(claims: Claims, service: Service) -> DefectStatsRead:
    return service.stats(claims["tenant_id"], viewer_user_id=claims["sub"])


@router.get(
    "/{defect_id}",
    response_model=DefectDetailRead,
    dependencies=[Depends(require_perm(PERM_DEFECT_READ))],
)
def get_defect(defect_id: str, claims: Claims, service: Service) -> DefectDetailRead:
    try:
        defect, actions = service.get_defect(claims["tenant_id"], defect_id, viewer_user_id=claims["sub"])
        return DefectDetailRead(
            defect=DefectCreateFromObservationRead.model_validate(defect),
            actions=[DefectActionRead.model_validate(action) for action in actions],
        )
    except (NotFoundError, ConflictError) as exc:
        _handle_defect_error(exc)
        raise


@router.post(
    "/{defect_id}/assign",
    response_model=DefectCreateFromObservationRead,
    dependencies=[Depends(require_perm(PERM_DEFECT_WRITE))],
)
def assign_defect(
    defect_id: str,
    payload: DefectAssignRequest,
    claims: Claims,
    service: Service,
) -> DefectCreateFromObservationRead:
    try:
        row = service.assign_defect(claims["tenant_id"], defect_id, payload, viewer_user_id=claims["sub"])
        return DefectCreateFromObservationRead.model_validate(row)
    except (NotFoundError, ConflictError) as exc:
        _handle_defect_error(exc)
        raise


@router.post(
    "/{defect_id}/status",
    response_model=DefectCreateFromObservationRead,
    dependencies=[Depends(require_perm(PERM_DEFECT_WRITE))],
)
def update_status(
    defect_id: str,
    payload: DefectStatusRequest,
    claims: Claims,
    service: Service,
) -> DefectCreateFromObservationRead:
    try:
        row = service.update_status(claims["tenant_id"], defect_id, payload, viewer_user_id=claims["sub"])
        return DefectCreateFromObservationRead.model_validate(row)
    except (NotFoundError, ConflictError) as exc:
        _handle_defect_error(exc)
        raise
