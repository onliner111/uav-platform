from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.api.deps import get_current_claims, require_perm
from app.domain.models import (
    CapacityForecastRead,
    CapacityForecastRequest,
    CapacityPolicyRead,
    CapacityPolicyUpsertRequest,
    ObservabilityAlertEventRead,
    ObservabilityAlertStatus,
    ObservabilityOverviewRead,
    ObservabilitySignalIngestRead,
    ObservabilitySignalIngestRequest,
    ObservabilitySignalLevel,
    ObservabilitySignalRead,
    ObservabilitySignalType,
    ObservabilitySloEvaluateRequest,
    ObservabilitySloEvaluateResultRead,
    ObservabilitySloEvaluationRead,
    ObservabilitySloOverviewRead,
    ObservabilitySloPolicyCreate,
    ObservabilitySloPolicyRead,
    ObservabilitySloStatus,
    ReliabilityBackupRunRead,
    ReliabilityBackupRunRequest,
    ReliabilityRestoreDrillRead,
    ReliabilityRestoreDrillRequest,
    SecurityInspectionItemRead,
    SecurityInspectionRunRead,
    SecurityInspectionRunRequest,
)
from app.domain.permissions import PERM_OBSERVABILITY_READ, PERM_OBSERVABILITY_WRITE
from app.infra.audit import set_audit_context
from app.services.observability_service import ConflictError, NotFoundError, ObservabilityService

router = APIRouter()


def get_observability_service() -> ObservabilityService:
    return ObservabilityService()


Claims = Annotated[dict[str, Any], Depends(get_current_claims)]
Service = Annotated[ObservabilityService, Depends(get_observability_service)]


def _handle_error(exc: Exception) -> None:
    if isinstance(exc, NotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if isinstance(exc, ConflictError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    raise exc


@router.post(
    "/signals:ingest",
    response_model=ObservabilitySignalIngestRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_perm(PERM_OBSERVABILITY_WRITE))],
)
def ingest_signals(
    payload: ObservabilitySignalIngestRequest,
    request: Request,
    claims: Claims,
    service: Service,
) -> ObservabilitySignalIngestRead:
    try:
        rows = service.ingest_signals(claims["tenant_id"], claims["sub"], payload)
        set_audit_context(
            request,
            action="observability.signals.ingest",
            resource="/api/observability/signals:ingest",
            detail={"what": {"accepted_count": len(rows)}},
        )
        return ObservabilitySignalIngestRead(
            accepted_count=len(rows),
            signals=[ObservabilitySignalRead.model_validate(item) for item in rows],
        )
    except (NotFoundError, ConflictError) as exc:
        _handle_error(exc)
        raise


@router.get(
    "/signals",
    response_model=list[ObservabilitySignalRead],
    dependencies=[Depends(require_perm(PERM_OBSERVABILITY_READ))],
)
def list_signals(
    claims: Claims,
    service: Service,
    signal_type: ObservabilitySignalType | None = None,
    level: ObservabilitySignalLevel | None = None,
    service_name: str | None = None,
    signal_name: str | None = None,
    trace_id: str | None = None,
    from_ts: datetime | None = None,
    to_ts: datetime | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[ObservabilitySignalRead]:
    rows = service.list_signals(
        claims["tenant_id"],
        signal_type=signal_type,
        level=level,
        service_name=service_name,
        signal_name=signal_name,
        trace_id=trace_id,
        from_ts=from_ts,
        to_ts=to_ts,
        limit=limit,
    )
    return [ObservabilitySignalRead.model_validate(item) for item in rows]


@router.get(
    "/overview",
    response_model=ObservabilityOverviewRead,
    dependencies=[Depends(require_perm(PERM_OBSERVABILITY_READ))],
)
def get_overview(
    claims: Claims,
    service: Service,
    window_minutes: int = Query(default=60, ge=1, le=1440),
) -> ObservabilityOverviewRead:
    return service.get_overview(claims["tenant_id"], window_minutes=window_minutes)


@router.post(
    "/slo/policies",
    response_model=ObservabilitySloPolicyRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_perm(PERM_OBSERVABILITY_WRITE))],
)
def create_slo_policy(
    payload: ObservabilitySloPolicyCreate,
    request: Request,
    claims: Claims,
    service: Service,
) -> ObservabilitySloPolicyRead:
    try:
        row = service.create_slo_policy(claims["tenant_id"], claims["sub"], payload)
        set_audit_context(
            request,
            action="observability.slo.policy.create",
            resource="/api/observability/slo/policies",
            detail={"what": {"policy_id": row.id, "policy_key": row.policy_key}},
        )
        return ObservabilitySloPolicyRead.model_validate(row)
    except (NotFoundError, ConflictError) as exc:
        _handle_error(exc)
        raise


@router.get(
    "/slo/policies",
    response_model=list[ObservabilitySloPolicyRead],
    dependencies=[Depends(require_perm(PERM_OBSERVABILITY_READ))],
)
def list_slo_policies(
    claims: Claims,
    service: Service,
    is_active: bool | None = None,
) -> list[ObservabilitySloPolicyRead]:
    rows = service.list_slo_policies(claims["tenant_id"], is_active=is_active)
    return [ObservabilitySloPolicyRead.model_validate(item) for item in rows]


@router.post(
    "/slo:evaluate",
    response_model=ObservabilitySloEvaluateResultRead,
    dependencies=[Depends(require_perm(PERM_OBSERVABILITY_WRITE))],
)
def evaluate_slo(
    payload: ObservabilitySloEvaluateRequest,
    request: Request,
    claims: Claims,
    service: Service,
) -> ObservabilitySloEvaluateResultRead:
    try:
        rows, alerts_created = service.evaluate_slo_policies(claims["tenant_id"], claims["sub"], payload)
        set_audit_context(
            request,
            action="observability.slo.evaluate",
            resource="/api/observability/slo:evaluate",
            detail={
                "what": {
                    "evaluated_count": len(rows),
                    "alerts_created": alerts_created,
                    "dry_run": payload.dry_run,
                }
            },
        )
        items = [ObservabilitySloEvaluationRead.model_validate(item) for item in rows]
        breached_count = len([item for item in items if item.status == ObservabilitySloStatus.BREACHED])
        return ObservabilitySloEvaluateResultRead(
            evaluated_count=len(items),
            breached_count=breached_count,
            alerts_created=alerts_created,
            items=items,
        )
    except (NotFoundError, ConflictError) as exc:
        _handle_error(exc)
        raise


@router.get(
    "/slo/evaluations",
    response_model=list[ObservabilitySloEvaluationRead],
    dependencies=[Depends(require_perm(PERM_OBSERVABILITY_READ))],
)
def list_slo_evaluations(
    claims: Claims,
    service: Service,
    slo_status: Annotated[ObservabilitySloStatus | None, Query(alias="status")] = None,
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[ObservabilitySloEvaluationRead]:
    rows = service.list_slo_evaluations(claims["tenant_id"], status=slo_status, limit=limit)
    return [ObservabilitySloEvaluationRead.model_validate(item) for item in rows]


@router.get(
    "/slo/overview",
    response_model=ObservabilitySloOverviewRead,
    dependencies=[Depends(require_perm(PERM_OBSERVABILITY_READ))],
)
def get_slo_overview(claims: Claims, service: Service) -> ObservabilitySloOverviewRead:
    return service.get_slo_overview(claims["tenant_id"])


@router.get(
    "/alerts",
    response_model=list[ObservabilityAlertEventRead],
    dependencies=[Depends(require_perm(PERM_OBSERVABILITY_READ))],
)
def list_observability_alerts(
    claims: Claims,
    service: Service,
    alert_status: Annotated[ObservabilityAlertStatus | None, Query(alias="status")] = None,
    source: str | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[ObservabilityAlertEventRead]:
    rows = service.list_alert_events(claims["tenant_id"], status=alert_status, source=source, limit=limit)
    return [ObservabilityAlertEventRead.model_validate(item) for item in rows]


@router.post(
    "/backups:runs",
    response_model=ReliabilityBackupRunRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_perm(PERM_OBSERVABILITY_WRITE))],
)
def run_backup(
    payload: ReliabilityBackupRunRequest,
    request: Request,
    claims: Claims,
    service: Service,
) -> ReliabilityBackupRunRead:
    row = service.run_backup(claims["tenant_id"], claims["sub"], payload)
    set_audit_context(
        request,
        action="observability.backup.run",
        resource="/api/observability/backups:runs",
        detail={"what": {"backup_run_id": row.id, "status": row.status.value}},
    )
    return ReliabilityBackupRunRead.model_validate(row)


@router.get(
    "/backups/runs",
    response_model=list[ReliabilityBackupRunRead],
    dependencies=[Depends(require_perm(PERM_OBSERVABILITY_READ))],
)
def list_backups(
    claims: Claims,
    service: Service,
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[ReliabilityBackupRunRead]:
    rows = service.list_backups(claims["tenant_id"], limit=limit)
    return [ReliabilityBackupRunRead.model_validate(item) for item in rows]


@router.post(
    "/backups/runs/{backup_run_id}:restore-drill",
    response_model=ReliabilityRestoreDrillRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_perm(PERM_OBSERVABILITY_WRITE))],
)
def run_restore_drill(
    backup_run_id: str,
    payload: ReliabilityRestoreDrillRequest,
    request: Request,
    claims: Claims,
    service: Service,
) -> ReliabilityRestoreDrillRead:
    try:
        row = service.run_restore_drill(claims["tenant_id"], backup_run_id, claims["sub"], payload)
        set_audit_context(
            request,
            action="observability.backup.restore_drill",
            resource=f"/api/observability/backups/runs/{backup_run_id}:restore-drill",
            detail={
                "what": {
                    "restore_drill_id": row.id,
                    "status": row.status.value,
                    "backup_run_id": backup_run_id,
                }
            },
        )
        return ReliabilityRestoreDrillRead.model_validate(row)
    except (NotFoundError, ConflictError) as exc:
        _handle_error(exc)
        raise


@router.get(
    "/backups/drills",
    response_model=list[ReliabilityRestoreDrillRead],
    dependencies=[Depends(require_perm(PERM_OBSERVABILITY_READ))],
)
def list_restore_drills(
    claims: Claims,
    service: Service,
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[ReliabilityRestoreDrillRead]:
    rows = service.list_restore_drills(claims["tenant_id"], limit=limit)
    return [ReliabilityRestoreDrillRead.model_validate(item) for item in rows]


@router.post(
    "/security-inspections:runs",
    response_model=SecurityInspectionRunRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_perm(PERM_OBSERVABILITY_WRITE))],
)
def run_security_inspection(
    payload: SecurityInspectionRunRequest,
    request: Request,
    claims: Claims,
    service: Service,
) -> SecurityInspectionRunRead:
    run, items = service.run_security_inspection(claims["tenant_id"], claims["sub"], payload)
    set_audit_context(
        request,
        action="observability.security_inspection.run",
        resource="/api/observability/security-inspections:runs",
        detail={
            "what": {
                "inspection_run_id": run.id,
                "failed_checks": run.failed_checks,
                "score_percent": run.score_percent,
            }
        },
    )
    return SecurityInspectionRunRead(
        **run.model_dump(),
        items=[SecurityInspectionItemRead.model_validate(item) for item in items],
    )


@router.get(
    "/security-inspections/runs",
    response_model=list[SecurityInspectionRunRead],
    dependencies=[Depends(require_perm(PERM_OBSERVABILITY_READ))],
)
def list_security_inspections(
    claims: Claims,
    service: Service,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[SecurityInspectionRunRead]:
    rows = service.list_security_inspections(claims["tenant_id"], limit=limit)
    return [
        SecurityInspectionRunRead(
            **run.model_dump(),
            items=[SecurityInspectionItemRead.model_validate(item) for item in items],
        )
        for run, items in rows
    ]


@router.put(
    "/capacity/policies/{meter_key}",
    response_model=CapacityPolicyRead,
    dependencies=[Depends(require_perm(PERM_OBSERVABILITY_WRITE))],
)
def upsert_capacity_policy(
    meter_key: str,
    payload: CapacityPolicyUpsertRequest,
    request: Request,
    claims: Claims,
    service: Service,
) -> CapacityPolicyRead:
    try:
        row = service.upsert_capacity_policy(claims["tenant_id"], meter_key, claims["sub"], payload)
        set_audit_context(
            request,
            action="observability.capacity.policy.upsert",
            resource=f"/api/observability/capacity/policies/{meter_key}",
            detail={"what": {"policy_id": row.id, "meter_key": row.meter_key}},
        )
        return CapacityPolicyRead.model_validate(row)
    except (NotFoundError, ConflictError) as exc:
        _handle_error(exc)
        raise


@router.get(
    "/capacity/policies",
    response_model=list[CapacityPolicyRead],
    dependencies=[Depends(require_perm(PERM_OBSERVABILITY_READ))],
)
def list_capacity_policies(
    claims: Claims,
    service: Service,
) -> list[CapacityPolicyRead]:
    rows = service.list_capacity_policies(claims["tenant_id"])
    return [CapacityPolicyRead.model_validate(item) for item in rows]


@router.post(
    "/capacity:forecast",
    response_model=CapacityForecastRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_perm(PERM_OBSERVABILITY_WRITE))],
)
def forecast_capacity(
    payload: CapacityForecastRequest,
    request: Request,
    claims: Claims,
    service: Service,
) -> CapacityForecastRead:
    try:
        row = service.forecast_capacity(claims["tenant_id"], payload)
        set_audit_context(
            request,
            action="observability.capacity.forecast",
            resource="/api/observability/capacity:forecast",
            detail={
                "what": {
                    "forecast_id": row.id,
                    "meter_key": row.meter_key,
                    "decision": row.decision.value,
                    "recommended_replicas": row.recommended_replicas,
                }
            },
        )
        return CapacityForecastRead.model_validate(row)
    except (NotFoundError, ConflictError) as exc:
        _handle_error(exc)
        raise


@router.get(
    "/capacity/forecasts",
    response_model=list[CapacityForecastRead],
    dependencies=[Depends(require_perm(PERM_OBSERVABILITY_READ))],
)
def list_capacity_forecasts(
    claims: Claims,
    service: Service,
    meter_key: str | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[CapacityForecastRead]:
    rows = service.list_capacity_forecasts(claims["tenant_id"], meter_key=meter_key, limit=limit)
    return [CapacityForecastRead.model_validate(item) for item in rows]
