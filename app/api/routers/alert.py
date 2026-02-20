from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_claims, require_perm
from app.domain.models import AlertActionRequest, AlertRead, AlertStatus
from app.domain.permissions import PERM_ALERT_READ, PERM_ALERT_WRITE
from app.services.alert_service import AlertService, ConflictError, NotFoundError

router = APIRouter()


def get_alert_service() -> AlertService:
    return AlertService()


Claims = Annotated[dict[str, Any], Depends(get_current_claims)]
Service = Annotated[AlertService, Depends(get_alert_service)]


def _handle_alert_error(exc: Exception) -> None:
    if isinstance(exc, NotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if isinstance(exc, ConflictError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    raise exc


@router.get(
    "/alerts",
    response_model=list[AlertRead],
    dependencies=[Depends(require_perm(PERM_ALERT_READ))],
)
def list_alerts(
    claims: Claims,
    service: Service,
    drone_id: str | None = None,
    alert_status: AlertStatus | None = None,
) -> list[AlertRead]:
    rows = service.list_alerts(
        claims["tenant_id"],
        drone_id=drone_id,
        status=alert_status,
    )
    return [AlertRead.model_validate(item) for item in rows]


@router.get(
    "/alerts/{alert_id}",
    response_model=AlertRead,
    dependencies=[Depends(require_perm(PERM_ALERT_READ))],
)
def get_alert(alert_id: str, claims: Claims, service: Service) -> AlertRead:
    try:
        row = service.get_alert(claims["tenant_id"], alert_id)
        return AlertRead.model_validate(row)
    except (NotFoundError, ConflictError) as exc:
        _handle_alert_error(exc)
        raise


@router.post(
    "/alerts/{alert_id}/ack",
    response_model=AlertRead,
    dependencies=[Depends(require_perm(PERM_ALERT_WRITE))],
)
def ack_alert(
    alert_id: str,
    payload: AlertActionRequest,
    claims: Claims,
    service: Service,
) -> AlertRead:
    try:
        row = service.ack_alert(
            claims["tenant_id"],
            alert_id,
            claims["sub"],
            comment=payload.comment,
        )
        return AlertRead.model_validate(row)
    except (NotFoundError, ConflictError) as exc:
        _handle_alert_error(exc)
        raise


@router.post(
    "/alerts/{alert_id}/close",
    response_model=AlertRead,
    dependencies=[Depends(require_perm(PERM_ALERT_WRITE))],
)
def close_alert(
    alert_id: str,
    payload: AlertActionRequest,
    claims: Claims,
    service: Service,
) -> AlertRead:
    try:
        row = service.close_alert(
            claims["tenant_id"],
            alert_id,
            claims["sub"],
            comment=payload.comment,
        )
        return AlertRead.model_validate(row)
    except (NotFoundError, ConflictError) as exc:
        _handle_alert_error(exc)
        raise
