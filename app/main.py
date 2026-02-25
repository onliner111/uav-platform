from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from app.api.routers import (
    ai,
    alert,
    approval,
    asset,
    asset_maintenance,
    command,
    compliance,
    dashboard,
    defect,
    identity,
    incident,
    inspection,
    kpi,
    map_router,
    mission,
    open_platform,
    outcomes,
    registry,
    reporting,
    task_center,
    telemetry,
    tenant_export,
    tenant_purge,
    ui,
)
from app.infra.audit import AuditMiddleware
from app.infra.db import check_db_ready
from app.infra.redis_state import check_redis_ready

app = FastAPI(
    title="uav-platform",
    description="Monolith + Adapter plugin architecture for UAV operations.",
    version="0.1.0-phase0",
)

app.add_middleware(AuditMiddleware)

app.include_router(identity.router, prefix="/api/identity", tags=["identity"])
app.include_router(asset.router, prefix="/api/assets", tags=["assets"])
app.include_router(
    asset_maintenance.router,
    prefix="/api/assets/maintenance",
    tags=["assets-maintenance"],
)
app.include_router(registry.router, prefix="/api/registry", tags=["registry"])
app.include_router(mission.router, prefix="/api/mission", tags=["mission"])
app.include_router(telemetry.router, prefix="/api/telemetry", tags=["telemetry"])
app.include_router(telemetry.ws_router, tags=["telemetry-ws"])
app.include_router(command.router, prefix="/api/command", tags=["command"])
app.include_router(compliance.router, prefix="/api/compliance", tags=["compliance"])
app.include_router(alert.router, prefix="/api/alert", tags=["alert"])
app.include_router(outcomes.router, prefix="/api/outcomes", tags=["outcomes"])
app.include_router(map_router.router, prefix="/api/map", tags=["map"])
app.include_router(task_center.router, prefix="/api/task-center", tags=["task-center"])
app.include_router(inspection.router, prefix="/api/inspection", tags=["inspection"])
app.include_router(defect.router, prefix="/api/defects", tags=["defects"])
app.include_router(incident.router, prefix="/api/incidents", tags=["incidents"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["dashboard"])
app.include_router(dashboard.ws_router, tags=["dashboard-ws"])
app.include_router(approval.router, prefix="/api/approvals", tags=["approvals"])
app.include_router(reporting.router, prefix="/api/reporting", tags=["reporting"])
app.include_router(ai.router, prefix="/api/ai", tags=["ai"])
app.include_router(kpi.router, prefix="/api/kpi", tags=["kpi"])
app.include_router(open_platform.router, prefix="/api/open-platform", tags=["open-platform"])
app.include_router(tenant_export.router, prefix="/api", tags=["tenant-export"])
app.include_router(tenant_purge.router, prefix="/api", tags=["tenant-purge"])
app.include_router(ui.router, tags=["ui"])

static_dir = Path("app") / "web" / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz")
def readyz() -> dict[str, object]:
    db_ok = check_db_ready()
    redis_ok = check_redis_ready()
    checks = {
        "db": "ok" if db_ok else "fail",
        "redis": "ok" if redis_ok else "fail",
    }
    if not (db_ok and redis_ok):
        raise HTTPException(
            status_code=503,
            detail={"status": "not_ready", "checks": checks},
        )
    return {"status": "ready", "checks": checks}
