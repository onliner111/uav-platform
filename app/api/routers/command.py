from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import require_perm
from app.domain.permissions import PERM_COMMAND_READ

router = APIRouter()


@router.get("/_phase0", dependencies=[Depends(require_perm(PERM_COMMAND_READ))])
def phase0_command() -> dict[str, str]:
    return {"module": "command", "status": "phase0-skeleton"}
