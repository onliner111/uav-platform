from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.api.deps import get_current_claims, require_perm
from app.domain.models import DroneCreate, DroneRead, DroneUpdate
from app.domain.permissions import PERM_REGISTRY_READ, PERM_REGISTRY_WRITE
from app.services.registry_service import ConflictError, NotFoundError, RegistryService

router = APIRouter()


def get_registry_service() -> RegistryService:
    return RegistryService()


Claims = Annotated[dict[str, Any], Depends(get_current_claims)]
Service = Annotated[RegistryService, Depends(get_registry_service)]


def _handle_registry_error(exc: Exception) -> None:
    if isinstance(exc, NotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if isinstance(exc, ConflictError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    raise exc


@router.post(
    "/drones",
    response_model=DroneRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_perm(PERM_REGISTRY_WRITE))],
)
def create_drone(payload: DroneCreate, claims: Claims, service: Service) -> DroneRead:
    try:
        drone = service.create_drone(claims["tenant_id"], payload)
        return DroneRead.model_validate(drone)
    except (NotFoundError, ConflictError) as exc:
        _handle_registry_error(exc)
        raise


@router.get(
    "/drones",
    response_model=list[DroneRead],
    dependencies=[Depends(require_perm(PERM_REGISTRY_READ))],
)
def list_drones(claims: Claims, service: Service) -> list[DroneRead]:
    drones = service.list_drones(claims["tenant_id"])
    return [DroneRead.model_validate(item) for item in drones]


@router.get(
    "/drones/{drone_id}",
    response_model=DroneRead,
    dependencies=[Depends(require_perm(PERM_REGISTRY_READ))],
)
def get_drone(drone_id: str, claims: Claims, service: Service) -> DroneRead:
    try:
        drone = service.get_drone(claims["tenant_id"], drone_id)
        return DroneRead.model_validate(drone)
    except (NotFoundError, ConflictError) as exc:
        _handle_registry_error(exc)
        raise


@router.patch(
    "/drones/{drone_id}",
    response_model=DroneRead,
    dependencies=[Depends(require_perm(PERM_REGISTRY_WRITE))],
)
def update_drone(drone_id: str, payload: DroneUpdate, claims: Claims, service: Service) -> DroneRead:
    try:
        drone = service.update_drone(claims["tenant_id"], drone_id, payload)
        return DroneRead.model_validate(drone)
    except (NotFoundError, ConflictError) as exc:
        _handle_registry_error(exc)
        raise


@router.delete(
    "/drones/{drone_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_perm(PERM_REGISTRY_WRITE))],
)
def delete_drone(drone_id: str, claims: Claims, service: Service) -> Response:
    try:
        service.delete_drone(claims["tenant_id"], drone_id)
    except (NotFoundError, ConflictError) as exc:
        _handle_registry_error(exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

