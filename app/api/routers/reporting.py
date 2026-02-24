from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.api.deps import get_current_claims, require_perm
from app.domain.models import (
    DeviceUtilizationRead,
    ReportingClosureRateRead,
    ReportingExportRequest,
    ReportingOverviewRead,
)
from app.domain.permissions import PERM_REPORTING_READ, PERM_REPORTING_WRITE
from app.services.reporting_service import ReportingService

router = APIRouter()


def get_reporting_service() -> ReportingService:
    return ReportingService()


Claims = Annotated[dict[str, Any], Depends(get_current_claims)]
Service = Annotated[ReportingService, Depends(get_reporting_service)]


@router.get(
    "/overview",
    response_model=ReportingOverviewRead,
    dependencies=[Depends(require_perm(PERM_REPORTING_READ))],
)
def reporting_overview(claims: Claims, service: Service) -> ReportingOverviewRead:
    return service.overview(claims["tenant_id"], viewer_user_id=claims["sub"])


@router.get(
    "/closure-rate",
    response_model=ReportingClosureRateRead,
    dependencies=[Depends(require_perm(PERM_REPORTING_READ))],
)
def reporting_closure_rate(claims: Claims, service: Service) -> ReportingClosureRateRead:
    return service.closure_rate(claims["tenant_id"], viewer_user_id=claims["sub"])


@router.get(
    "/device-utilization",
    response_model=list[DeviceUtilizationRead],
    dependencies=[Depends(require_perm(PERM_REPORTING_READ))],
)
def reporting_device_utilization(claims: Claims, service: Service) -> list[DeviceUtilizationRead]:
    return service.device_utilization(claims["tenant_id"], viewer_user_id=claims["sub"])


@router.post(
    "/export",
    dependencies=[Depends(require_perm(PERM_REPORTING_WRITE))],
)
def reporting_export(
    payload: ReportingExportRequest,
    claims: Claims,
    service: Service,
) -> dict[str, str]:
    return {"file_path": service.export_report(claims["tenant_id"], payload, viewer_user_id=claims["sub"])}
