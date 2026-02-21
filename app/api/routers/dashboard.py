from __future__ import annotations

import asyncio
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect

from app.api.deps import get_current_claims, require_perm
from app.domain.models import DashboardStatsRead
from app.domain.permissions import PERM_DASHBOARD_READ, has_permission
from app.infra.auth import decode_access_token
from app.services.dashboard_service import DashboardService

router = APIRouter()
ws_router = APIRouter()


def get_dashboard_service() -> DashboardService:
    return DashboardService()


Claims = Annotated[dict[str, Any], Depends(get_current_claims)]
Service = Annotated[DashboardService, Depends(get_dashboard_service)]


def _extract_ws_token(websocket: WebSocket, token: str | None) -> str | None:
    if token:
        return token
    auth_header = websocket.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()
    return None


@router.get(
    "/stats",
    response_model=DashboardStatsRead,
    dependencies=[Depends(require_perm(PERM_DASHBOARD_READ))],
)
def get_stats(claims: Claims, service: Service) -> DashboardStatsRead:
    return service.get_stats(claims["tenant_id"])


@router.get(
    "/observations",
    dependencies=[Depends(require_perm(PERM_DASHBOARD_READ))],
)
def latest_observations(claims: Claims, service: Service, limit: int = Query(default=100, ge=1, le=500)) -> list[dict[str, Any]]:
    rows = service.latest_observations(claims["tenant_id"], limit=limit)
    return [
        {
            "id": item.id,
            "task_id": item.task_id,
            "lat": item.position_lat,
            "lon": item.position_lon,
            "severity": item.severity,
            "note": item.note,
            "ts": item.ts.isoformat(),
        }
        for item in rows
    ]


@ws_router.websocket("/ws/dashboard")
async def ws_dashboard(websocket: WebSocket, token: str | None = Query(default=None)) -> None:
    resolved_token = _extract_ws_token(websocket, token)
    if not resolved_token:
        await websocket.close(code=4401)
        return
    try:
        claims = decode_access_token(resolved_token)
    except Exception:
        await websocket.close(code=4401)
        return
    if not has_permission(claims, PERM_DASHBOARD_READ):
        await websocket.close(code=4403)
        return
    tenant_id = claims.get("tenant_id")
    if not isinstance(tenant_id, str) or not tenant_id:
        await websocket.close(code=4401)
        return

    await websocket.accept()
    service = DashboardService()
    try:
        while True:
            stats = service.get_stats(tenant_id)
            markers = service.latest_observations(tenant_id, limit=50)
            await websocket.send_json(
                {
                    "stats": stats.model_dump(),
                    "markers": [
                        {
                            "id": item.id,
                            "lat": item.position_lat,
                            "lon": item.position_lon,
                            "severity": item.severity,
                            "note": item.note,
                            "ts": item.ts.isoformat(),
                        }
                        for item in markers
                    ],
                }
            )
            await asyncio.sleep(2.0)
    except WebSocketDisconnect:
        return
    except Exception:
        await websocket.close(code=1011)
