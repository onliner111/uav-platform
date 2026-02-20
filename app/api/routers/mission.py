from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import require_perm
from app.domain.permissions import PERM_MISSION_READ

router = APIRouter()


@router.get("/_phase0", dependencies=[Depends(require_perm(PERM_MISSION_READ))])
def phase0_mission() -> dict[str, str]:
    return {"module": "mission", "status": "phase0-skeleton"}
