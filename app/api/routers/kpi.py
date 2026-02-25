from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_claims, require_perm
from app.domain.models import (
    KpiGovernanceExportRead,
    KpiGovernanceExportRequest,
    KpiHeatmapBinRead,
    KpiHeatmapSource,
    KpiSnapshotRead,
    KpiSnapshotRecomputeRequest,
)
from app.domain.permissions import PERM_REPORTING_READ, PERM_REPORTING_WRITE
from app.services.kpi_service import ConflictError, KpiService, NotFoundError

router = APIRouter()


def get_kpi_service() -> KpiService:
    return KpiService()


Claims = Annotated[dict[str, Any], Depends(get_current_claims)]
Service = Annotated[KpiService, Depends(get_kpi_service)]


def _handle_kpi_error(exc: Exception) -> None:
    if isinstance(exc, NotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if isinstance(exc, ConflictError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    raise exc


@router.post(
    "/snapshots/recompute",
    response_model=KpiSnapshotRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_perm(PERM_REPORTING_WRITE))],
)
def recompute_snapshot(
    payload: KpiSnapshotRecomputeRequest,
    claims: Claims,
    service: Service,
) -> KpiSnapshotRead:
    try:
        row = service.recompute_snapshot(claims["tenant_id"], claims["sub"], payload)
        return KpiSnapshotRead.model_validate(row)
    except (NotFoundError, ConflictError) as exc:
        _handle_kpi_error(exc)
        raise


@router.get(
    "/snapshots",
    response_model=list[KpiSnapshotRead],
    dependencies=[Depends(require_perm(PERM_REPORTING_READ))],
)
def list_snapshots(
    claims: Claims,
    service: Service,
    from_ts: datetime | None = None,
    to_ts: datetime | None = None,
) -> list[KpiSnapshotRead]:
    rows = service.list_snapshots(claims["tenant_id"], from_ts=from_ts, to_ts=to_ts)
    return [KpiSnapshotRead.model_validate(item) for item in rows]


@router.get(
    "/snapshots/latest",
    response_model=KpiSnapshotRead,
    dependencies=[Depends(require_perm(PERM_REPORTING_READ))],
)
def get_latest_snapshot(claims: Claims, service: Service) -> KpiSnapshotRead:
    try:
        row = service.get_latest_snapshot(claims["tenant_id"])
        return KpiSnapshotRead.model_validate(row)
    except (NotFoundError, ConflictError) as exc:
        _handle_kpi_error(exc)
        raise


@router.get(
    "/heatmap",
    response_model=list[KpiHeatmapBinRead],
    dependencies=[Depends(require_perm(PERM_REPORTING_READ))],
)
def list_heatmap(
    claims: Claims,
    service: Service,
    snapshot_id: str | None = None,
    source: KpiHeatmapSource | None = None,
) -> list[KpiHeatmapBinRead]:
    try:
        rows = service.list_heatmap_bins(claims["tenant_id"], snapshot_id=snapshot_id, source=source)
        return [KpiHeatmapBinRead.model_validate(item) for item in rows]
    except (NotFoundError, ConflictError) as exc:
        _handle_kpi_error(exc)
        raise


@router.post(
    "/governance/export",
    response_model=KpiGovernanceExportRead,
    dependencies=[Depends(require_perm(PERM_REPORTING_WRITE))],
)
def export_governance_report(
    payload: KpiGovernanceExportRequest,
    claims: Claims,
    service: Service,
) -> KpiGovernanceExportRead:
    try:
        file_path = service.export_governance_report(claims["tenant_id"], claims["sub"], payload)
        return KpiGovernanceExportRead(file_path=file_path)
    except (NotFoundError, ConflictError) as exc:
        _handle_kpi_error(exc)
        raise
