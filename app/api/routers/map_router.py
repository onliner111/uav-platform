from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_current_claims, require_perm
from app.domain.models import MapLayerRead, MapOverviewRead, MapTrackReplayRead
from app.domain.permissions import PERM_DASHBOARD_READ
from app.services.map_service import MapService, NotFoundError

router = APIRouter()


def get_map_service() -> MapService:
    return MapService()


Claims = Annotated[dict[str, Any], Depends(get_current_claims)]
Service = Annotated[MapService, Depends(get_map_service)]


def _handle_map_error(exc: Exception) -> None:
    if isinstance(exc, NotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    raise exc


@router.get(
    "/overview",
    response_model=MapOverviewRead,
    dependencies=[Depends(require_perm(PERM_DASHBOARD_READ))],
)
def get_map_overview(
    claims: Claims,
    service: Service,
    limit_per_layer: int = Query(default=100, ge=1, le=500),
) -> MapOverviewRead:
    return service.overview(
        claims["tenant_id"],
        viewer_user_id=claims["sub"],
        limit_per_layer=limit_per_layer,
    )


@router.get(
    "/layers/resources",
    response_model=MapLayerRead,
    dependencies=[Depends(require_perm(PERM_DASHBOARD_READ))],
)
def get_resource_layer(
    claims: Claims,
    service: Service,
    limit: int = Query(default=100, ge=1, le=500),
) -> MapLayerRead:
    return service.resources_layer(claims["tenant_id"], limit=limit)


@router.get(
    "/layers/tasks",
    response_model=MapLayerRead,
    dependencies=[Depends(require_perm(PERM_DASHBOARD_READ))],
)
def get_task_layer(
    claims: Claims,
    service: Service,
    limit: int = Query(default=100, ge=1, le=500),
) -> MapLayerRead:
    return service.tasks_layer(claims["tenant_id"], viewer_user_id=claims["sub"], limit=limit)


@router.get(
    "/layers/alerts",
    response_model=MapLayerRead,
    dependencies=[Depends(require_perm(PERM_DASHBOARD_READ))],
)
def get_alert_layer(
    claims: Claims,
    service: Service,
    limit: int = Query(default=100, ge=1, le=500),
) -> MapLayerRead:
    return service.alerts_layer(claims["tenant_id"], limit=limit)


@router.get(
    "/layers/events",
    response_model=MapLayerRead,
    dependencies=[Depends(require_perm(PERM_DASHBOARD_READ))],
)
def get_event_layer(
    claims: Claims,
    service: Service,
    limit: int = Query(default=100, ge=1, le=500),
) -> MapLayerRead:
    return service.events_layer(claims["tenant_id"], viewer_user_id=claims["sub"], limit=limit)


@router.get(
    "/tracks/replay",
    response_model=MapTrackReplayRead,
    dependencies=[Depends(require_perm(PERM_DASHBOARD_READ))],
)
def replay_track(
    claims: Claims,
    service: Service,
    drone_id: str = Query(..., min_length=1),
    from_ts: datetime | None = None,
    to_ts: datetime | None = None,
    sample_step: int = Query(default=1, ge=1, le=20),
    limit: int = Query(default=500, ge=1, le=2000),
) -> MapTrackReplayRead:
    try:
        return service.replay_track(
            claims["tenant_id"],
            drone_id=drone_id,
            from_ts=from_ts,
            to_ts=to_ts,
            sample_step=sample_step,
            limit=limit,
        )
    except NotFoundError as exc:
        _handle_map_error(exc)
        raise
