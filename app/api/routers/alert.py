from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_claims, require_perm
from app.domain.models import (
    AlertActionRequest,
    AlertHandlingActionCreate,
    AlertHandlingActionRead,
    AlertPriority,
    AlertRead,
    AlertReviewRead,
    AlertRouteLogRead,
    AlertRoutingRuleCreate,
    AlertRoutingRuleRead,
    AlertStatus,
    AlertType,
)
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


@router.post(
    "/routing-rules",
    response_model=AlertRoutingRuleRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_perm(PERM_ALERT_WRITE))],
)
def create_routing_rule(
    payload: AlertRoutingRuleCreate,
    claims: Claims,
    service: Service,
) -> AlertRoutingRuleRead:
    try:
        row = service.create_routing_rule(claims["tenant_id"], claims["sub"], payload)
        return AlertRoutingRuleRead.model_validate(row)
    except (NotFoundError, ConflictError) as exc:
        _handle_alert_error(exc)
        raise


@router.get(
    "/routing-rules",
    response_model=list[AlertRoutingRuleRead],
    dependencies=[Depends(require_perm(PERM_ALERT_READ))],
)
def list_routing_rules(
    claims: Claims,
    service: Service,
    priority_level: AlertPriority | None = None,
    alert_type: AlertType | None = None,
    is_active: bool | None = None,
) -> list[AlertRoutingRuleRead]:
    rows = service.list_routing_rules(
        claims["tenant_id"],
        priority_level=priority_level,
        alert_type=alert_type,
        is_active=is_active,
    )
    return [AlertRoutingRuleRead.model_validate(item) for item in rows]


@router.get(
    "/alerts/{alert_id}/routes",
    response_model=list[AlertRouteLogRead],
    dependencies=[Depends(require_perm(PERM_ALERT_READ))],
)
def list_alert_routes(alert_id: str, claims: Claims, service: Service) -> list[AlertRouteLogRead]:
    try:
        rows = service.list_alert_routes(claims["tenant_id"], alert_id)
        return [AlertRouteLogRead.model_validate(item) for item in rows]
    except (NotFoundError, ConflictError) as exc:
        _handle_alert_error(exc)
        raise


@router.post(
    "/alerts/{alert_id}/actions",
    response_model=AlertHandlingActionRead,
    dependencies=[Depends(require_perm(PERM_ALERT_WRITE))],
)
def create_alert_action(
    alert_id: str,
    payload: AlertHandlingActionCreate,
    claims: Claims,
    service: Service,
) -> AlertHandlingActionRead:
    try:
        row = service.create_handling_action(claims["tenant_id"], alert_id, claims["sub"], payload)
        return AlertHandlingActionRead.model_validate(row)
    except (NotFoundError, ConflictError) as exc:
        _handle_alert_error(exc)
        raise


@router.get(
    "/alerts/{alert_id}/actions",
    response_model=list[AlertHandlingActionRead],
    dependencies=[Depends(require_perm(PERM_ALERT_READ))],
)
def list_alert_actions(alert_id: str, claims: Claims, service: Service) -> list[AlertHandlingActionRead]:
    try:
        rows = service.list_handling_actions(claims["tenant_id"], alert_id)
        return [AlertHandlingActionRead.model_validate(item) for item in rows]
    except (NotFoundError, ConflictError) as exc:
        _handle_alert_error(exc)
        raise


@router.get(
    "/alerts/{alert_id}/review",
    response_model=AlertReviewRead,
    dependencies=[Depends(require_perm(PERM_ALERT_READ))],
)
def get_alert_review(alert_id: str, claims: Claims, service: Service) -> AlertReviewRead:
    try:
        alert, routes, actions = service.get_alert_review(claims["tenant_id"], alert_id)
        return AlertReviewRead(
            alert=AlertRead.model_validate(alert),
            routes=[AlertRouteLogRead.model_validate(item) for item in routes],
            actions=[AlertHandlingActionRead.model_validate(item) for item in actions],
        )
    except (NotFoundError, ConflictError) as exc:
        _handle_alert_error(exc)
        raise
