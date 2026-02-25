from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.deps import get_current_claims, require_perm
from app.domain.models import (
    AirspaceZoneCreate,
    AirspaceZoneRead,
    AirspaceZoneType,
    MissionPreflightChecklistInitRequest,
    MissionPreflightChecklistItemCheckRequest,
    MissionPreflightChecklistRead,
    PreflightChecklistTemplateCreate,
    PreflightChecklistTemplateRead,
)
from app.domain.permissions import PERM_MISSION_READ, PERM_MISSION_WRITE
from app.infra.audit import set_audit_context
from app.services.compliance_service import (
    ComplianceService,
    ComplianceViolationError,
    ConflictError,
    NotFoundError,
)

router = APIRouter()


def get_compliance_service() -> ComplianceService:
    return ComplianceService()


Claims = Annotated[dict[str, Any], Depends(get_current_claims)]
Service = Annotated[ComplianceService, Depends(get_compliance_service)]


def _handle_error(exc: Exception) -> None:
    if isinstance(exc, NotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if isinstance(exc, ComplianceViolationError):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "reason_code": exc.reason_code.value,
                "message": str(exc),
                "detail": exc.detail,
            },
        ) from exc
    if isinstance(exc, ConflictError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    raise exc


@router.post(
    "/zones",
    response_model=AirspaceZoneRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_perm(PERM_MISSION_WRITE))],
)
def create_zone(
    payload: AirspaceZoneCreate,
    request: Request,
    claims: Claims,
    service: Service,
) -> AirspaceZoneRead:
    set_audit_context(
        request,
        action="compliance.airspace_zone.create",
        detail={"what": {"zone_type": payload.zone_type, "name": payload.name}},
    )
    try:
        row = service.create_airspace_zone(claims["tenant_id"], claims["sub"], payload)
        return AirspaceZoneRead.model_validate(row)
    except (NotFoundError, ConflictError, ComplianceViolationError) as exc:
        _handle_error(exc)
        raise


@router.get(
    "/zones",
    response_model=list[AirspaceZoneRead],
    dependencies=[Depends(require_perm(PERM_MISSION_READ))],
)
def list_zones(
    claims: Claims,
    service: Service,
    zone_type: AirspaceZoneType | None = None,
    is_active: bool | None = None,
) -> list[AirspaceZoneRead]:
    rows = service.list_airspace_zones(claims["tenant_id"], zone_type=zone_type, is_active=is_active)
    return [AirspaceZoneRead.model_validate(item) for item in rows]


@router.get(
    "/zones/{zone_id}",
    response_model=AirspaceZoneRead,
    dependencies=[Depends(require_perm(PERM_MISSION_READ))],
)
def get_zone(zone_id: str, claims: Claims, service: Service) -> AirspaceZoneRead:
    try:
        row = service.get_airspace_zone(claims["tenant_id"], zone_id)
        return AirspaceZoneRead.model_validate(row)
    except (NotFoundError, ConflictError, ComplianceViolationError) as exc:
        _handle_error(exc)
        raise


@router.post(
    "/preflight/templates",
    response_model=PreflightChecklistTemplateRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_perm(PERM_MISSION_WRITE))],
)
def create_preflight_template(
    payload: PreflightChecklistTemplateCreate,
    request: Request,
    claims: Claims,
    service: Service,
) -> PreflightChecklistTemplateRead:
    set_audit_context(
        request,
        action="compliance.preflight_template.create",
        detail={"what": {"name": payload.name}},
    )
    try:
        row = service.create_preflight_template(claims["tenant_id"], claims["sub"], payload)
        return PreflightChecklistTemplateRead.model_validate(row)
    except (NotFoundError, ConflictError, ComplianceViolationError) as exc:
        _handle_error(exc)
        raise


@router.get(
    "/preflight/templates",
    response_model=list[PreflightChecklistTemplateRead],
    dependencies=[Depends(require_perm(PERM_MISSION_READ))],
)
def list_preflight_templates(
    claims: Claims,
    service: Service,
    is_active: bool | None = None,
) -> list[PreflightChecklistTemplateRead]:
    rows = service.list_preflight_templates(claims["tenant_id"], is_active=is_active)
    return [PreflightChecklistTemplateRead.model_validate(item) for item in rows]


@router.post(
    "/missions/{mission_id}/preflight/init",
    response_model=MissionPreflightChecklistRead,
    dependencies=[Depends(require_perm(PERM_MISSION_WRITE))],
)
def init_mission_preflight(
    mission_id: str,
    payload: MissionPreflightChecklistInitRequest,
    request: Request,
    claims: Claims,
    service: Service,
) -> MissionPreflightChecklistRead:
    set_audit_context(
        request,
        action="compliance.preflight.init",
        detail={"what": {"mission_id": mission_id}},
    )
    try:
        row = service.init_mission_preflight_checklist(claims["tenant_id"], mission_id, claims["sub"], payload)
        return MissionPreflightChecklistRead.model_validate(row)
    except (NotFoundError, ConflictError, ComplianceViolationError) as exc:
        _handle_error(exc)
        raise


@router.get(
    "/missions/{mission_id}/preflight",
    response_model=MissionPreflightChecklistRead,
    dependencies=[Depends(require_perm(PERM_MISSION_READ))],
)
def get_mission_preflight(
    mission_id: str,
    claims: Claims,
    service: Service,
) -> MissionPreflightChecklistRead:
    try:
        row = service.get_mission_preflight_checklist(claims["tenant_id"], mission_id)
        return MissionPreflightChecklistRead.model_validate(row)
    except (NotFoundError, ConflictError, ComplianceViolationError) as exc:
        _handle_error(exc)
        raise


@router.post(
    "/missions/{mission_id}/preflight/check-item",
    response_model=MissionPreflightChecklistRead,
    dependencies=[Depends(require_perm(PERM_MISSION_WRITE))],
)
def check_mission_preflight_item(
    mission_id: str,
    payload: MissionPreflightChecklistItemCheckRequest,
    request: Request,
    claims: Claims,
    service: Service,
) -> MissionPreflightChecklistRead:
    set_audit_context(
        request,
        action="compliance.preflight.check_item",
        detail={"what": {"mission_id": mission_id, "item_code": payload.item_code}},
    )
    try:
        row = service.check_mission_preflight_item(claims["tenant_id"], mission_id, claims["sub"], payload)
        return MissionPreflightChecklistRead.model_validate(row)
    except (NotFoundError, ConflictError, ComplianceViolationError) as exc:
        _handle_error(exc)
        raise
