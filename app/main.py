from __future__ import annotations

from fastapi import FastAPI, HTTPException

from app.api.routers import alert, command, identity, mission, registry, telemetry
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
app.include_router(registry.router, prefix="/api/registry", tags=["registry"])
app.include_router(mission.router, prefix="/api/mission", tags=["mission"])
app.include_router(telemetry.router, prefix="/api/telemetry", tags=["telemetry"])
app.include_router(telemetry.ws_router, tags=["telemetry-ws"])
app.include_router(command.router, prefix="/api/command", tags=["command"])
app.include_router(alert.router, prefix="/api/alert", tags=["alert"])


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
