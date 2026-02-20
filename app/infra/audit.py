from __future__ import annotations

from typing import Any

from sqlmodel import Session
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.domain.models import AuditLog
from app.infra.db import engine

WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def write_audit_log(
    *,
    tenant_id: str,
    actor_id: str | None,
    action: str,
    resource: str,
    method: str,
    status_code: int,
    detail: dict[str, Any] | None = None,
) -> None:
    log = AuditLog(
        tenant_id=tenant_id,
        actor_id=actor_id,
        action=action,
        resource=resource,
        method=method,
        status_code=status_code,
        detail=detail or {},
    )
    with Session(engine) as session:
        session.add(log)
        session.commit()


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        if request.method not in WRITE_METHODS:
            return response
        if request.url.path in {"/healthz", "/readyz"}:
            return response

        claims = getattr(request.state, "claims", {})
        tenant_id = claims.get("tenant_id", "system")
        actor_id = claims.get("sub")
        try:
            write_audit_log(
                tenant_id=tenant_id,
                actor_id=actor_id,
                action=f"{request.method}:{request.url.path}",
                resource=request.url.path,
                method=request.method,
                status_code=response.status_code,
            )
        except Exception:
            # Audit must not block request flow in Phase 0.
            return response
        return response
