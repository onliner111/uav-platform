from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.api.deps import get_current_claims, require_perm
from app.domain.models import CommandDispatchRequest, CommandRead
from app.domain.permissions import PERM_COMMAND_READ, PERM_COMMAND_WRITE
from app.services.command_service import CommandService, ConflictError, NotFoundError
from app.services.compliance_service import ComplianceViolationError

router = APIRouter()


def get_command_service() -> CommandService:
    return CommandService()


Claims = Annotated[dict[str, Any], Depends(get_current_claims)]
Service = Annotated[CommandService, Depends(get_command_service)]


def _handle_command_error(exc: Exception) -> None:
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
    "/commands",
    response_model=CommandRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_perm(PERM_COMMAND_WRITE))],
)
async def dispatch_command(
    payload: CommandDispatchRequest,
    claims: Claims,
    response: Response,
    service: Service,
) -> CommandRead:
    try:
        record, created = await service.dispatch_command(
            tenant_id=claims["tenant_id"],
            actor_id=claims["sub"],
            payload=payload,
        )
        if not created:
            response.status_code = status.HTTP_200_OK
        return CommandRead.model_validate(record)
    except (NotFoundError, ConflictError, ComplianceViolationError) as exc:
        _handle_command_error(exc)
        raise


@router.get(
    "/commands",
    response_model=list[CommandRead],
    dependencies=[Depends(require_perm(PERM_COMMAND_READ))],
)
def list_commands(claims: Claims, service: Service) -> list[CommandRead]:
    records = service.list_commands(claims["tenant_id"])
    return [CommandRead.model_validate(item) for item in records]


@router.get(
    "/commands/{command_id}",
    response_model=CommandRead,
    dependencies=[Depends(require_perm(PERM_COMMAND_READ))],
)
def get_command(command_id: str, claims: Claims, service: Service) -> CommandRead:
    try:
        record = service.get_command(claims["tenant_id"], command_id)
        return CommandRead.model_validate(record)
    except (NotFoundError, ConflictError, ComplianceViolationError) as exc:
        _handle_command_error(exc)
        raise
