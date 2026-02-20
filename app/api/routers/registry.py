from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import require_perm
from app.domain.permissions import PERM_REGISTRY_READ

router = APIRouter()


@router.get("/_phase0", dependencies=[Depends(require_perm(PERM_REGISTRY_READ))])
def phase0_registry() -> dict[str, str]:
    return {"module": "registry", "status": "phase0-skeleton"}
