from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.api.deps import get_current_claims, require_perm
from app.domain.models import ApprovalRecordCreate, ApprovalRecordRead
from app.domain.permissions import PERM_APPROVAL_READ, PERM_APPROVAL_WRITE
from app.services.compliance_service import ComplianceService

router = APIRouter()


def get_compliance_service() -> ComplianceService:
    return ComplianceService()


Claims = Annotated[dict[str, Any], Depends(get_current_claims)]
Service = Annotated[ComplianceService, Depends(get_compliance_service)]


@router.post(
    "",
    response_model=ApprovalRecordRead,
    dependencies=[Depends(require_perm(PERM_APPROVAL_WRITE))],
)
def create_approval(payload: ApprovalRecordCreate, claims: Claims, service: Service) -> ApprovalRecordRead:
    row = service.create_approval(claims["tenant_id"], claims["sub"], payload)
    return ApprovalRecordRead.model_validate(row)


@router.get(
    "",
    response_model=list[ApprovalRecordRead],
    dependencies=[Depends(require_perm(PERM_APPROVAL_READ))],
)
def list_approvals(
    claims: Claims,
    service: Service,
    entity_type: str | None = None,
    entity_id: str | None = None,
) -> list[ApprovalRecordRead]:
    rows = service.list_approvals(claims["tenant_id"], entity_type=entity_type, entity_id=entity_id)
    return [ApprovalRecordRead.model_validate(item) for item in rows]


@router.get(
    "/audit-export",
    dependencies=[Depends(require_perm(PERM_APPROVAL_READ))],
)
def audit_export(claims: Claims, service: Service) -> dict[str, str]:
    return {"file_path": service.export_audit(claims["tenant_id"])}
