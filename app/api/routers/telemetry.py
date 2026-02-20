from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status

from app.api.deps import get_current_claims, require_perm
from app.domain.models import TelemetryNormalized
from app.domain.permissions import PERM_TELEMETRY_READ, PERM_TELEMETRY_WRITE, has_permission
from app.infra.auth import decode_access_token
from app.services.telemetry_service import NotFoundError, TelemetryService

router = APIRouter()
ws_router = APIRouter()


class TelemetryWsHub:
    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = {}

    async def connect(self, tenant_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.setdefault(tenant_id, set()).add(websocket)

    def disconnect(self, tenant_id: str, websocket: WebSocket) -> None:
        tenant_conns = self._connections.get(tenant_id, set())
        if websocket in tenant_conns:
            tenant_conns.remove(websocket)
        if not tenant_conns and tenant_id in self._connections:
            del self._connections[tenant_id]

    async def broadcast(self, tenant_id: str, payload: dict[str, Any]) -> None:
        connections = list(self._connections.get(tenant_id, set()))
        for connection in connections:
            try:
                await connection.send_json(payload)
            except Exception:
                self.disconnect(tenant_id, connection)


telemetry_ws_hub = TelemetryWsHub()


def get_telemetry_service() -> TelemetryService:
    return TelemetryService()


Claims = Annotated[dict[str, Any], Depends(get_current_claims)]
Service = Annotated[TelemetryService, Depends(get_telemetry_service)]


def _extract_ws_token(websocket: WebSocket, token: str | None) -> str | None:
    if token:
        return token
    auth_header = websocket.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()
    return None


def _handle_telemetry_not_found(exc: NotFoundError) -> None:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/ingest",
    response_model=TelemetryNormalized,
    dependencies=[Depends(require_perm(PERM_TELEMETRY_WRITE))],
)
async def ingest_telemetry(
    payload: TelemetryNormalized,
    claims: Claims,
    service: Service,
) -> TelemetryNormalized:
    normalized = service.ingest(claims["tenant_id"], payload)
    await telemetry_ws_hub.broadcast(claims["tenant_id"], normalized.model_dump(mode="json"))
    return normalized


@router.get(
    "/drones/{drone_id}/latest",
    response_model=TelemetryNormalized,
    dependencies=[Depends(require_perm(PERM_TELEMETRY_READ))],
)
def get_latest_telemetry(drone_id: str, claims: Claims, service: Service) -> TelemetryNormalized:
    try:
        return service.get_latest(claims["tenant_id"], drone_id)
    except NotFoundError as exc:
        _handle_telemetry_not_found(exc)
        raise


@ws_router.websocket("/ws/drones")
async def ws_drones(websocket: WebSocket, token: str | None = Query(default=None)) -> None:
    resolved_token = _extract_ws_token(websocket, token)
    if not resolved_token:
        await websocket.close(code=4401)
        return
    try:
        claims = decode_access_token(resolved_token)
    except Exception:
        await websocket.close(code=4401)
        return
    if not has_permission(claims, PERM_TELEMETRY_READ):
        await websocket.close(code=4403)
        return
    tenant_id = claims.get("tenant_id")
    if not isinstance(tenant_id, str) or not tenant_id:
        await websocket.close(code=4401)
        return

    await telemetry_ws_hub.connect(tenant_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        telemetry_ws_hub.disconnect(tenant_id, websocket)

