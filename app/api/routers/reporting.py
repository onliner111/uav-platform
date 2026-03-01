from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request

from app.api.deps import get_current_claims, require_perm
from app.domain.models import (
    DeviceUtilizationRead,
    OutcomeReportExportCreateRequest,
    OutcomeReportExportRead,
    OutcomeReportRetentionRunRead,
    OutcomeReportRetentionRunRequest,
    OutcomeReportTemplateCreate,
    OutcomeReportTemplateRead,
    ReportExportStatus,
    ReportingClosureRateRead,
    ReportingExportRequest,
    ReportingOverviewRead,
)
from app.domain.permissions import PERM_REPORTING_READ, PERM_REPORTING_WRITE
from app.infra.audit import set_audit_context
from app.services.reporting_service import (
    ConflictError,
    NotFoundError,
    ReportingService,
)

router = APIRouter()


def get_reporting_service() -> ReportingService:
    return ReportingService()


Claims = Annotated[dict[str, Any], Depends(get_current_claims)]
Service = Annotated[ReportingService, Depends(get_reporting_service)]


def _handle_reporting_error(exc: Exception) -> None:
    from fastapi import HTTPException, status

    if isinstance(exc, NotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if isinstance(exc, ConflictError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    raise exc


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


@router.post(
    "/outcome-report-templates",
    response_model=OutcomeReportTemplateRead,
    status_code=201,
    dependencies=[Depends(require_perm(PERM_REPORTING_WRITE))],
)
def create_outcome_report_template(
    payload: OutcomeReportTemplateCreate,
    claims: Claims,
    service: Service,
    request: Request,
) -> OutcomeReportTemplateRead:
    set_audit_context(
        request,
        action="reporting.outcome_report.template.create",
        detail={"what": {"template_name": payload.name}},
    )
    try:
        row = service.create_outcome_report_template(claims["tenant_id"], claims["sub"], payload)
        return OutcomeReportTemplateRead.model_validate(row)
    except (NotFoundError, ConflictError) as exc:
        _handle_reporting_error(exc)
        raise


@router.get(
    "/outcome-report-templates",
    response_model=list[OutcomeReportTemplateRead],
    dependencies=[Depends(require_perm(PERM_REPORTING_READ))],
)
def list_outcome_report_templates(
    claims: Claims,
    service: Service,
) -> list[OutcomeReportTemplateRead]:
    rows = service.list_outcome_report_templates(claims["tenant_id"])
    return [OutcomeReportTemplateRead.model_validate(item) for item in rows]


@router.post(
    "/outcome-report-exports",
    response_model=OutcomeReportExportRead,
    status_code=201,
    dependencies=[Depends(require_perm(PERM_REPORTING_WRITE))],
)
def create_outcome_report_export(
    payload: OutcomeReportExportCreateRequest,
    claims: Claims,
    service: Service,
    request: Request,
) -> OutcomeReportExportRead:
    set_audit_context(
        request,
        action="reporting.outcome_report.export.create",
        detail={
            "what": {
                "template_id": payload.template_id,
                "report_format": payload.report_format,
                "task_id": payload.task_id,
                "from_ts": payload.from_ts.isoformat() if payload.from_ts else None,
                "to_ts": payload.to_ts.isoformat() if payload.to_ts else None,
                "topic": payload.topic,
            }
        },
    )
    try:
        row = service.create_outcome_report_export(
            claims["tenant_id"],
            claims["sub"],
            payload,
            viewer_user_id=claims["sub"],
        )
        return OutcomeReportExportRead.model_validate(row)
    except (NotFoundError, ConflictError) as exc:
        _handle_reporting_error(exc)
        raise


@router.get(
    "/outcome-report-exports",
    response_model=list[OutcomeReportExportRead],
    dependencies=[Depends(require_perm(PERM_REPORTING_READ))],
)
def list_outcome_report_exports(
    claims: Claims,
    service: Service,
    status_filter: ReportExportStatus | None = None,
    limit: int = 50,
) -> list[OutcomeReportExportRead]:
    rows = service.list_outcome_report_exports(claims["tenant_id"], status=status_filter, limit=limit)
    return [OutcomeReportExportRead.model_validate(item) for item in rows]


@router.get(
    "/outcome-report-exports/{export_id}",
    response_model=OutcomeReportExportRead,
    dependencies=[Depends(require_perm(PERM_REPORTING_READ))],
)
def get_outcome_report_export(
    export_id: str,
    claims: Claims,
    service: Service,
    request: Request,
) -> OutcomeReportExportRead:
    set_audit_context(
        request,
        action="reporting.outcome_report.export.get",
        detail={"what": {"export_id": export_id}},
    )
    try:
        row = service.get_outcome_report_export(claims["tenant_id"], export_id)
        return OutcomeReportExportRead.model_validate(row)
    except (NotFoundError, ConflictError) as exc:
        _handle_reporting_error(exc)
        raise


@router.post(
    "/outcome-report-exports:retention",
    response_model=OutcomeReportRetentionRunRead,
    dependencies=[Depends(require_perm(PERM_REPORTING_WRITE))],
)
def run_outcome_report_retention(
    payload: OutcomeReportRetentionRunRequest,
    claims: Claims,
    service: Service,
    request: Request,
) -> OutcomeReportRetentionRunRead:
    set_audit_context(
        request,
        action="reporting.outcome_report.retention.run",
        detail={
            "what": {
                "retention_days": payload.retention_days,
                "dry_run": payload.dry_run,
            }
        },
    )
    try:
        return service.run_outcome_report_retention(claims["tenant_id"], payload)
    except (NotFoundError, ConflictError) as exc:
        _handle_reporting_error(exc)
        raise
