from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.api.deps import get_current_claims, require_perm
from app.domain.models import (
    ApprovalRead,
    MissionApprovalRequest,
    MissionCreate,
    MissionRead,
    MissionTransitionRequest,
    MissionUpdate,
)
from app.domain.permissions import PERM_MISSION_APPROVE, PERM_MISSION_READ, PERM_MISSION_WRITE
from app.services.compliance_service import ComplianceViolationError
from app.services.mission_service import (
    ConflictError,
    MissionService,
    NotFoundError,
    PermissionDeniedError,
)

router = APIRouter()


def get_mission_service() -> MissionService:
    return MissionService()


Claims = Annotated[dict[str, Any], Depends(get_current_claims)]
Service = Annotated[MissionService, Depends(get_mission_service)]


def _handle_mission_error(exc: Exception) -> None:
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
    if isinstance(exc, PermissionDeniedError):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    raise exc


@router.post(
    "/missions",
    response_model=MissionRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_perm(PERM_MISSION_WRITE))],
)
def create_mission(payload: MissionCreate, claims: Claims, service: Service) -> MissionRead:
    try:
        mission = service.create_mission(
            tenant_id=claims["tenant_id"],
            actor_id=claims["sub"],
            permissions=claims.get("permissions", []),
            payload=payload,
        )
        return MissionRead.model_validate(mission)
    except (NotFoundError, ConflictError, PermissionDeniedError, ComplianceViolationError) as exc:
        _handle_mission_error(exc)
        raise


@router.get(
    "/missions",
    response_model=list[MissionRead],
    dependencies=[Depends(require_perm(PERM_MISSION_READ))],
)
def list_missions(claims: Claims, service: Service) -> list[MissionRead]:
    missions = service.list_missions(claims["tenant_id"], viewer_user_id=claims["sub"])
    return [MissionRead.model_validate(item) for item in missions]


@router.get(
    "/missions/{mission_id}",
    response_model=MissionRead,
    dependencies=[Depends(require_perm(PERM_MISSION_READ))],
)
def get_mission(mission_id: str, claims: Claims, service: Service) -> MissionRead:
    try:
        mission = service.get_mission(claims["tenant_id"], mission_id, viewer_user_id=claims["sub"])
        return MissionRead.model_validate(mission)
    except (NotFoundError, ConflictError, PermissionDeniedError, ComplianceViolationError) as exc:
        _handle_mission_error(exc)
        raise


@router.patch(
    "/missions/{mission_id}",
    response_model=MissionRead,
    dependencies=[Depends(require_perm(PERM_MISSION_WRITE))],
)
def update_mission(
    mission_id: str,
    payload: MissionUpdate,
    claims: Claims,
    service: Service,
) -> MissionRead:
    try:
        mission = service.update_mission(
            tenant_id=claims["tenant_id"],
            mission_id=mission_id,
            actor_id=claims["sub"],
            permissions=claims.get("permissions", []),
            payload=payload,
            viewer_user_id=claims["sub"],
        )
        return MissionRead.model_validate(mission)
    except (NotFoundError, ConflictError, PermissionDeniedError, ComplianceViolationError) as exc:
        _handle_mission_error(exc)
        raise


@router.delete(
    "/missions/{mission_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_perm(PERM_MISSION_WRITE))],
)
def delete_mission(mission_id: str, claims: Claims, service: Service) -> Response:
    try:
        service.delete_mission(claims["tenant_id"], mission_id, viewer_user_id=claims["sub"])
    except (NotFoundError, ConflictError, PermissionDeniedError) as exc:
        _handle_mission_error(exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/missions/{mission_id}/approve",
    response_model=MissionRead,
    dependencies=[Depends(require_perm(PERM_MISSION_APPROVE))],
)
def approve_mission(
    mission_id: str,
    payload: MissionApprovalRequest,
    claims: Claims,
    service: Service,
) -> MissionRead:
    try:
        mission, _approval = service.approve_mission(
            tenant_id=claims["tenant_id"],
            mission_id=mission_id,
            actor_id=claims["sub"],
            payload=payload,
            viewer_user_id=claims["sub"],
        )
        return MissionRead.model_validate(mission)
    except (NotFoundError, ConflictError, PermissionDeniedError, ComplianceViolationError) as exc:
        _handle_mission_error(exc)
        raise


@router.get(
    "/missions/{mission_id}/approvals",
    response_model=list[ApprovalRead],
    dependencies=[Depends(require_perm(PERM_MISSION_READ))],
)
def list_mission_approvals(mission_id: str, claims: Claims, service: Service) -> list[ApprovalRead]:
    try:
        approvals = service.list_approvals(claims["tenant_id"], mission_id, viewer_user_id=claims["sub"])
        return [ApprovalRead.model_validate(item) for item in approvals]
    except (NotFoundError, ConflictError, PermissionDeniedError, ComplianceViolationError) as exc:
        _handle_mission_error(exc)
        raise


@router.post(
    "/missions/{mission_id}/transition",
    response_model=MissionRead,
    dependencies=[Depends(require_perm(PERM_MISSION_WRITE))],
)
def transition_mission(
    mission_id: str,
    payload: MissionTransitionRequest,
    claims: Claims,
    service: Service,
) -> MissionRead:
    try:
        mission = service.transition_mission(
            tenant_id=claims["tenant_id"],
            mission_id=mission_id,
            actor_id=claims["sub"],
            permissions=claims.get("permissions", []),
            payload=payload,
            viewer_user_id=claims["sub"],
        )
        return MissionRead.model_validate(mission)
    except (NotFoundError, ConflictError, PermissionDeniedError, ComplianceViolationError) as exc:
        _handle_mission_error(exc)
        raise

