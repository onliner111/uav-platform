from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import require_perm
from app.domain.permissions import PERM_TELEMETRY_READ

router = APIRouter()


@router.get("/_phase0", dependencies=[Depends(require_perm(PERM_TELEMETRY_READ))])
def phase0_telemetry() -> dict[str, str]:
    return {"module": "telemetry", "status": "phase0-skeleton"}
