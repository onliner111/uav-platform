from __future__ import annotations

from typing import Any

from sqlmodel import Session
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.domain.models import AuditLog, now_utc
from app.infra.db import engine

WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
AUDITED_READ_PATH_KEYWORDS = ("/export", "-export", "/download")
AUDIT_CONTEXT_STATE_KEY = "_audit_context"


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


def _deep_merge(base: dict[str, Any], extra: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in extra.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
            continue
        merged[key] = value
    return merged


def _status_outcome(status_code: int) -> str:
    if status_code >= 500:
        return "error"
    if status_code in {401, 403, 404}:
        return "denied"
    if status_code >= 400:
        return "rejected"
    return "success"


def should_audit_request(method: str, path: str) -> bool:
    if method in WRITE_METHODS:
        return True
    return any(keyword in path for keyword in AUDITED_READ_PATH_KEYWORDS)


def set_audit_context(
    request: Request,
    *,
    action: str | None = None,
    resource: str | None = None,
    detail: dict[str, Any] | None = None,
) -> None:
    context_raw = getattr(request.state, AUDIT_CONTEXT_STATE_KEY, {})
    context = dict(context_raw) if isinstance(context_raw, dict) else {}

    if action is not None:
        context["action"] = action
    if resource is not None:
        context["resource"] = resource

    if detail:
        previous_detail = context.get("detail")
        if isinstance(previous_detail, dict):
            context["detail"] = _deep_merge(previous_detail, detail)
        else:
            context["detail"] = detail

    setattr(request.state, AUDIT_CONTEXT_STATE_KEY, context)


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        path = request.url.path
        method = request.method
        if path in {"/healthz", "/readyz"}:
            return response
        context_raw = getattr(request.state, AUDIT_CONTEXT_STATE_KEY, {})
        context = context_raw if isinstance(context_raw, dict) else {}
        has_explicit_context = any(key in context for key in ("action", "resource", "detail"))
        if not should_audit_request(method, path) and not has_explicit_context:
            return response

        claims = getattr(request.state, "claims", {})
        tenant_id = claims.get("tenant_id", "system")
        actor_id = claims.get("sub")
        raw_action = context.get("action")
        raw_resource = context.get("resource")
        action: str = raw_action if isinstance(raw_action, str) else f"{method}:{path}"
        resource: str = raw_resource if isinstance(raw_resource, str) else path

        route = request.scope.get("route")
        route_path = getattr(route, "path", path)
        base_detail: dict[str, Any] = {
            "who": {
                "tenant_id": tenant_id,
                "actor_id": actor_id,
            },
            "when": {
                "request_ts": now_utc().isoformat(),
            },
            "where": {
                "path": path,
                "route": route_path,
                "query": request.url.query,
                "client_ip": request.client.host if request.client is not None else None,
            },
            "what": {
                "action": action,
                "resource": resource,
                "method": method,
            },
            "result": {
                "status_code": response.status_code,
                "outcome": _status_outcome(response.status_code),
            },
        }
        context_detail = context.get("detail")
        detail = _deep_merge(base_detail, context_detail) if isinstance(context_detail, dict) else base_detail

        try:
            write_audit_log(
                tenant_id=tenant_id,
                actor_id=actor_id,
                action=action,
                resource=resource,
                method=method,
                status_code=response.status_code,
                detail=detail,
            )
        except Exception:
            # Audit must not block request flow in Phase 0.
            return response
        return response
