from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_claims, require_perm
from app.domain.models import (
    OutcomeCatalogCreate,
    OutcomeCatalogRead,
    OutcomeCatalogStatusUpdateRequest,
    OutcomeSourceType,
    OutcomeStatus,
    OutcomeType,
    RawDataCatalogCreate,
    RawDataCatalogRead,
    RawDataType,
)
from app.domain.permissions import PERM_INSPECTION_READ, PERM_INSPECTION_WRITE
from app.services.outcome_service import ConflictError, NotFoundError, OutcomeService

router = APIRouter()


def get_outcome_service() -> OutcomeService:
    return OutcomeService()


Claims = Annotated[dict[str, Any], Depends(get_current_claims)]
Service = Annotated[OutcomeService, Depends(get_outcome_service)]


def _handle_outcome_error(exc: Exception) -> None:
    if isinstance(exc, NotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if isinstance(exc, ConflictError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    raise exc


@router.post(
    "/raw",
    response_model=RawDataCatalogRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_perm(PERM_INSPECTION_WRITE))],
)
def create_raw_data(payload: RawDataCatalogCreate, claims: Claims, service: Service) -> RawDataCatalogRead:
    try:
        row = service.create_raw_record(claims["tenant_id"], claims["sub"], payload)
        return RawDataCatalogRead.model_validate(row)
    except (NotFoundError, ConflictError) as exc:
        _handle_outcome_error(exc)
        raise


@router.get(
    "/raw",
    response_model=list[RawDataCatalogRead],
    dependencies=[Depends(require_perm(PERM_INSPECTION_READ))],
)
def list_raw_data(
    claims: Claims,
    service: Service,
    task_id: str | None = None,
    mission_id: str | None = None,
    data_type: RawDataType | None = None,
    from_ts: datetime | None = None,
    to_ts: datetime | None = None,
) -> list[RawDataCatalogRead]:
    rows = service.list_raw_records(
        claims["tenant_id"],
        task_id=task_id,
        mission_id=mission_id,
        data_type=data_type,
        from_ts=from_ts,
        to_ts=to_ts,
        viewer_user_id=claims["sub"],
    )
    return [RawDataCatalogRead.model_validate(item) for item in rows]


@router.post(
    "/records",
    response_model=OutcomeCatalogRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_perm(PERM_INSPECTION_WRITE))],
)
def create_outcome_record(
    payload: OutcomeCatalogCreate,
    claims: Claims,
    service: Service,
) -> OutcomeCatalogRead:
    try:
        row = service.create_outcome_record(claims["tenant_id"], claims["sub"], payload)
        return OutcomeCatalogRead.model_validate(row)
    except (NotFoundError, ConflictError) as exc:
        _handle_outcome_error(exc)
        raise


@router.post(
    "/records/from-observation/{observation_id}",
    response_model=OutcomeCatalogRead,
    dependencies=[Depends(require_perm(PERM_INSPECTION_WRITE))],
)
def materialize_from_observation(
    observation_id: str,
    claims: Claims,
    service: Service,
) -> OutcomeCatalogRead:
    try:
        row = service.materialize_outcome_from_observation(claims["tenant_id"], claims["sub"], observation_id)
        return OutcomeCatalogRead.model_validate(row)
    except (NotFoundError, ConflictError) as exc:
        _handle_outcome_error(exc)
        raise


@router.get(
    "/records",
    response_model=list[OutcomeCatalogRead],
    dependencies=[Depends(require_perm(PERM_INSPECTION_READ))],
)
def list_outcome_records(
    claims: Claims,
    service: Service,
    task_id: str | None = None,
    mission_id: str | None = None,
    source_type: OutcomeSourceType | None = None,
    outcome_type: OutcomeType | None = None,
    outcome_status: OutcomeStatus | None = None,
    from_ts: datetime | None = None,
    to_ts: datetime | None = None,
) -> list[OutcomeCatalogRead]:
    rows = service.list_outcome_records(
        claims["tenant_id"],
        task_id=task_id,
        mission_id=mission_id,
        source_type=source_type,
        outcome_type=outcome_type,
        status=outcome_status,
        from_ts=from_ts,
        to_ts=to_ts,
        viewer_user_id=claims["sub"],
    )
    return [OutcomeCatalogRead.model_validate(item) for item in rows]


@router.patch(
    "/records/{outcome_id}/status",
    response_model=OutcomeCatalogRead,
    dependencies=[Depends(require_perm(PERM_INSPECTION_WRITE))],
)
def update_outcome_status(
    outcome_id: str,
    payload: OutcomeCatalogStatusUpdateRequest,
    claims: Claims,
    service: Service,
) -> OutcomeCatalogRead:
    try:
        row = service.update_outcome_status(claims["tenant_id"], outcome_id, claims["sub"], payload)
        return OutcomeCatalogRead.model_validate(row)
    except (NotFoundError, ConflictError) as exc:
        _handle_outcome_error(exc)
        raise
