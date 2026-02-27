from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.api.deps import get_current_claims, require_perm
from app.domain.models import (
    DeviceIntegrationSessionRead,
    DeviceIntegrationStartRequest,
    VideoStreamCreateRequest,
    VideoStreamRead,
    VideoStreamUpdateRequest,
)
from app.domain.permissions import (
    PERM_DASHBOARD_READ,
    PERM_REGISTRY_READ,
    PERM_REGISTRY_WRITE,
)
from app.infra.audit import set_audit_context
from app.services.integration_service import ConflictError, IntegrationService, NotFoundError

router = APIRouter()


def get_integration_service() -> IntegrationService:
    return IntegrationService()


Claims = Annotated[dict[str, Any], Depends(get_current_claims)]
Service = Annotated[IntegrationService, Depends(get_integration_service)]


def _handle_integration_error(exc: Exception) -> None:
    if isinstance(exc, NotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if isinstance(exc, ConflictError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    raise exc


@router.post(
    "/device-sessions/start",
    response_model=DeviceIntegrationSessionRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_perm(PERM_REGISTRY_WRITE))],
)
async def start_device_session(
    payload: DeviceIntegrationStartRequest,
    request: Request,
    claims: Claims,
    service: Service,
) -> DeviceIntegrationSessionRead:
    try:
        row = await service.start_device_session(claims["tenant_id"], payload)
        set_audit_context(
            request,
            action="integration.device_session.start",
            resource="/api/integration/device-sessions/start",
            detail={
                "what": {
                    "session_id": row.session_id,
                    "drone_id": row.drone_id,
                    "adapter_vendor": row.adapter_vendor.value,
                    "simulation_mode": row.simulation_mode,
                }
            },
        )
        return row
    except (NotFoundError, ConflictError) as exc:
        _handle_integration_error(exc)
        raise


@router.post(
    "/device-sessions/{session_id}:stop",
    response_model=DeviceIntegrationSessionRead,
    dependencies=[Depends(require_perm(PERM_REGISTRY_WRITE))],
)
async def stop_device_session(
    session_id: str,
    request: Request,
    claims: Claims,
    service: Service,
) -> DeviceIntegrationSessionRead:
    try:
        row = await service.stop_device_session(claims["tenant_id"], session_id)
        set_audit_context(
            request,
            action="integration.device_session.stop",
            resource=f"/api/integration/device-sessions/{session_id}:stop",
            detail={
                "what": {
                    "session_id": row.session_id,
                    "drone_id": row.drone_id,
                    "status": row.status.value,
                    "samples_ingested": row.samples_ingested,
                }
            },
        )
        return row
    except (NotFoundError, ConflictError) as exc:
        _handle_integration_error(exc)
        raise


@router.get(
    "/device-sessions",
    response_model=list[DeviceIntegrationSessionRead],
    dependencies=[Depends(require_perm(PERM_REGISTRY_READ))],
)
def list_device_sessions(claims: Claims, service: Service) -> list[DeviceIntegrationSessionRead]:
    return service.list_device_sessions(claims["tenant_id"])


@router.get(
    "/device-sessions/{session_id}",
    response_model=DeviceIntegrationSessionRead,
    dependencies=[Depends(require_perm(PERM_REGISTRY_READ))],
)
def get_device_session(
    session_id: str,
    claims: Claims,
    service: Service,
) -> DeviceIntegrationSessionRead:
    try:
        return service.get_device_session(claims["tenant_id"], session_id)
    except (NotFoundError, ConflictError) as exc:
        _handle_integration_error(exc)
        raise


@router.post(
    "/video-streams",
    response_model=VideoStreamRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_perm(PERM_REGISTRY_WRITE))],
)
def create_video_stream(
    payload: VideoStreamCreateRequest,
    request: Request,
    claims: Claims,
    service: Service,
) -> VideoStreamRead:
    try:
        row = service.create_video_stream(claims["tenant_id"], payload)
        set_audit_context(
            request,
            action="integration.video_stream.create",
            resource="/api/integration/video-streams",
            detail={
                "what": {
                    "stream_id": row.stream_id,
                    "stream_key": row.stream_key,
                    "protocol": row.protocol.value,
                    "drone_id": row.drone_id,
                }
            },
        )
        return row
    except (NotFoundError, ConflictError) as exc:
        _handle_integration_error(exc)
        raise


@router.get(
    "/video-streams",
    response_model=list[VideoStreamRead],
    dependencies=[Depends(require_perm(PERM_DASHBOARD_READ))],
)
def list_video_streams(claims: Claims, service: Service) -> list[VideoStreamRead]:
    return service.list_video_streams(claims["tenant_id"])


@router.get(
    "/video-streams/{stream_id}",
    response_model=VideoStreamRead,
    dependencies=[Depends(require_perm(PERM_DASHBOARD_READ))],
)
def get_video_stream(stream_id: str, claims: Claims, service: Service) -> VideoStreamRead:
    try:
        return service.get_video_stream(claims["tenant_id"], stream_id)
    except (NotFoundError, ConflictError) as exc:
        _handle_integration_error(exc)
        raise


@router.patch(
    "/video-streams/{stream_id}",
    response_model=VideoStreamRead,
    dependencies=[Depends(require_perm(PERM_REGISTRY_WRITE))],
)
def update_video_stream(
    stream_id: str,
    payload: VideoStreamUpdateRequest,
    request: Request,
    claims: Claims,
    service: Service,
) -> VideoStreamRead:
    try:
        row = service.update_video_stream(claims["tenant_id"], stream_id, payload)
        set_audit_context(
            request,
            action="integration.video_stream.update",
            resource=f"/api/integration/video-streams/{stream_id}",
            detail={
                "what": {
                    "stream_id": row.stream_id,
                    "stream_key": row.stream_key,
                    "status": row.status.value,
                    "drone_id": row.drone_id,
                }
            },
        )
        return row
    except (NotFoundError, ConflictError) as exc:
        _handle_integration_error(exc)
        raise


@router.delete(
    "/video-streams/{stream_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_perm(PERM_REGISTRY_WRITE))],
)
def delete_video_stream(
    stream_id: str,
    request: Request,
    claims: Claims,
    service: Service,
) -> Response:
    try:
        service.delete_video_stream(claims["tenant_id"], stream_id)
        set_audit_context(
            request,
            action="integration.video_stream.delete",
            resource=f"/api/integration/video-streams/{stream_id}",
            detail={"what": {"stream_id": stream_id}},
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except (NotFoundError, ConflictError) as exc:
        _handle_integration_error(exc)
        raise
