from __future__ import annotations

import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

from fastapi import APIRouter, Form, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from app.domain.models import Tenant
from app.domain.permissions import (
    PERM_ALERT_READ,
    PERM_APPROVAL_READ,
    PERM_DASHBOARD_READ,
    PERM_DEFECT_READ,
    PERM_IDENTITY_READ,
    PERM_INCIDENT_READ,
    PERM_INSPECTION_READ,
    PERM_MISSION_READ,
    PERM_REGISTRY_READ,
    PERM_REPORTING_READ,
    has_permission,
)
from app.infra.auth import create_access_token, decode_access_token
from app.infra.db import get_engine
from app.services.dashboard_service import DashboardService
from app.services.defect_service import DefectService
from app.services.identity_service import AuthError, IdentityService, NotFoundError
from app.services.incident_service import IncidentService
from app.services.inspection_service import InspectionService

router = APIRouter()
templates = Jinja2Templates(directory=str(Path("app") / "web" / "templates"))

SESSION_COOKIE_NAME = "uav_ui_session"
CSRF_COOKIE_NAME = "uav_ui_csrf"
SESSION_MAX_AGE_SECONDS = 60 * 60 * 8
DEFAULT_NEXT_PATH = "/ui/console"


@dataclass(frozen=True)
class ConsoleNavItem:
    key: str
    label: str
    href: str
    description: str
    required_permission: str | None = None


NAV_ITEMS: tuple[ConsoleNavItem, ...] = (
    ConsoleNavItem(
        key="console",
        label="Workbench",
        href="/ui/console",
        description="Cross-module operation workspace and entry.",
    ),
    ConsoleNavItem(
        key="command-center",
        label="Command Center",
        href="/ui/command-center",
        description="Realtime map, stream and dashboard views.",
        required_permission=PERM_DASHBOARD_READ,
    ),
    ConsoleNavItem(
        key="inspection",
        label="Inspection",
        href="/ui/inspection",
        description="Inspection task and observation list.",
        required_permission=PERM_INSPECTION_READ,
    ),
    ConsoleNavItem(
        key="defects",
        label="Defects",
        href="/ui/defects",
        description="Defect closure workflow and quick actions.",
        required_permission=PERM_DEFECT_READ,
    ),
    ConsoleNavItem(
        key="emergency",
        label="Emergency",
        href="/ui/emergency",
        description="Emergency dispatch and incident launch.",
        required_permission=PERM_INCIDENT_READ,
    ),
    ConsoleNavItem(
        key="task-center",
        label="Task Center",
        href="/ui/task-center",
        description="Task lifecycle and workflow entry.",
        required_permission=PERM_MISSION_READ,
    ),
    ConsoleNavItem(
        key="assets",
        label="Assets",
        href="/ui/assets",
        description="Device and asset ledger entry.",
        required_permission=PERM_REGISTRY_READ,
    ),
    ConsoleNavItem(
        key="compliance",
        label="Compliance",
        href="/ui/compliance",
        description="Approval and compliance capability entry.",
        required_permission=PERM_APPROVAL_READ,
    ),
    ConsoleNavItem(
        key="alerts",
        label="Alerts",
        href="/ui/alerts",
        description="Alert routing and handling entry.",
        required_permission=PERM_ALERT_READ,
    ),
    ConsoleNavItem(
        key="reports",
        label="Reports",
        href="/ui/reports",
        description="Reporting and KPI output entry.",
        required_permission=PERM_REPORTING_READ,
    ),
    ConsoleNavItem(
        key="platform",
        label="Platform",
        href="/ui/platform",
        description="Tenant, role, and platform governance entry.",
        required_permission=PERM_IDENTITY_READ,
    ),
)


def _resolve_claims(token: str | None) -> dict[str, Any]:
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="token is required")
    try:
        claims = decode_access_token(token)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token") from exc
    if not isinstance(claims.get("tenant_id"), str):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token tenant")
    if not isinstance(claims.get("sub"), str):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token subject")
    if not isinstance(claims.get("permissions"), list):
        claims["permissions"] = []
    return claims


def _sanitize_next_path(next_path: str | None) -> str:
    if not next_path:
        return DEFAULT_NEXT_PATH
    parsed = urlparse(next_path)
    if parsed.scheme or parsed.netloc:
        return DEFAULT_NEXT_PATH
    if not parsed.path.startswith("/ui"):
        return DEFAULT_NEXT_PATH
    sanitized = parsed.path or DEFAULT_NEXT_PATH
    if parsed.query:
        sanitized = f"{sanitized}?{parsed.query}"
    return sanitized


def _new_csrf_token() -> str:
    return secrets.token_urlsafe(24)


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=SESSION_MAX_AGE_SECONDS,
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(key=SESSION_COOKIE_NAME, path="/")


def _set_csrf_cookie(response: Response, csrf_token: str) -> None:
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=csrf_token,
        httponly=False,
        samesite="strict",
        max_age=SESSION_MAX_AGE_SECONDS,
        path="/",
    )


def _ensure_csrf_cookie(request: Request, response: Response) -> str:
    csrf_token = request.cookies.get(CSRF_COOKIE_NAME)
    if csrf_token and isinstance(csrf_token, str):
        return csrf_token
    csrf_token = _new_csrf_token()
    _set_csrf_cookie(response, csrf_token)
    return csrf_token


def _verify_csrf(request: Request, csrf_token: str) -> None:
    csrf_cookie = request.cookies.get(CSRF_COOKIE_NAME)
    if not csrf_cookie or not csrf_token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid csrf token")
    if not secrets.compare_digest(csrf_cookie, csrf_token):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid csrf token")


def _tenant_options() -> list[dict[str, str]]:
    with Session(get_engine(), expire_on_commit=False) as session:
        rows = list(session.exec(select(Tenant).order_by(Tenant.name)).all())
    return [{"id": item.id, "name": item.name} for item in rows]


def _render_login(
    request: Request,
    *,
    next_path: str,
    selected_tenant: str = "",
    username: str = "",
    error_message: str | None = None,
    status_code: int = status.HTTP_200_OK,
) -> Response:
    csrf_token = request.cookies.get(CSRF_COOKIE_NAME) or _new_csrf_token()
    response = templates.TemplateResponse(
        request=request,
        name="ui_login.html",
        context={
            "next_path": next_path,
            "tenant_options": _tenant_options(),
            "selected_tenant": selected_tenant,
            "username": username,
            "error_message": error_message,
            "csrf_token": csrf_token,
        },
        status_code=status_code,
    )
    _set_csrf_cookie(response, csrf_token)
    return response


def _resolve_ui_access(
    request: Request,
    *,
    token: str | None,
    required_permission: str | None = None,
) -> tuple[str, dict[str, Any], bool]:
    from_query = False
    if token:
        claims = _resolve_claims(token)
        resolved_token = token
        from_query = True
    else:
        session_token = request.cookies.get(SESSION_COOKIE_NAME)
        claims = _resolve_claims(session_token)
        resolved_token = session_token or ""

    if required_permission and not has_permission(claims, required_permission):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"missing permission: {required_permission}")
    return resolved_token, claims, from_query


def _login_redirect(request: Request, *, clear_session: bool) -> RedirectResponse:
    requested_path = request.url.path
    if request.url.query:
        requested_path = f"{requested_path}?{request.url.query}"
    encoded_next = quote(requested_path, safe="")
    response = RedirectResponse(
        url=f"/ui/login?next={encoded_next}",
        status_code=status.HTTP_303_SEE_OTHER,
    )
    if clear_session:
        _clear_session_cookie(response)
    return response


def _is_nav_visible(claims: dict[str, Any], item: ConsoleNavItem) -> bool:
    if item.required_permission is None:
        return True
    return has_permission(claims, item.required_permission)


def _visible_nav_items(claims: dict[str, Any], active_key: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in NAV_ITEMS:
        if not _is_nav_visible(claims, item):
            continue
        rows.append(
            {
                "key": item.key,
                "label": item.label,
                "href": item.href,
                "description": item.description,
                "active": item.key == active_key,
            }
        )
    return rows


def _console_context(
    request: Request,
    *,
    token: str,
    claims: dict[str, Any],
    active_nav: str,
    title: str,
    subtitle: str,
    **extra: Any,
) -> dict[str, Any]:
    nav_rows = _visible_nav_items(claims, active_nav)
    active_label = next((item["label"] for item in nav_rows if item["active"]), "Workbench")
    context: dict[str, Any] = {
        "request": request,
        "page_title": title,
        "page_subtitle": subtitle,
        "tenant_id": claims["tenant_id"],
        "user_id": claims["sub"],
        "token": token,
        "csrf_token": request.cookies.get(CSRF_COOKIE_NAME, ""),
        "permissions": claims.get("permissions", []),
        "nav_items": nav_rows,
        "module_entries": [item for item in nav_rows if item["key"] != "console"],
        "breadcrumbs": ["Console", active_label],
    }
    context.update(extra)
    return context


def _render_console(
    request: Request,
    *,
    template_name: str,
    token: str,
    claims: dict[str, Any],
    active_nav: str,
    title: str,
    subtitle: str,
    session_from_query: bool,
    **extra: Any,
) -> Response:
    csrf_token = request.cookies.get(CSRF_COOKIE_NAME) or _new_csrf_token()
    response = templates.TemplateResponse(
        request=request,
        name=template_name,
        context=_console_context(
            request,
            token=token,
            claims=claims,
            active_nav=active_nav,
            title=title,
            subtitle=subtitle,
            csrf_token=csrf_token,
            **extra,
        ),
    )
    if not request.cookies.get(CSRF_COOKIE_NAME):
        _set_csrf_cookie(response, csrf_token)
    if session_from_query:
        _set_session_cookie(response, token)
    return response


@router.get("/ui")
def ui_root(request: Request, token: str | None = Query(default=None)) -> RedirectResponse:
    if token:
        try:
            _ = _resolve_claims(token)
        except HTTPException:
            return _login_redirect(request, clear_session=True)
        response = RedirectResponse(url=DEFAULT_NEXT_PATH, status_code=status.HTTP_303_SEE_OTHER)
        _set_session_cookie(response, token)
        _ensure_csrf_cookie(request, response)
        return response

    session_token = request.cookies.get(SESSION_COOKIE_NAME)
    if session_token:
        try:
            _ = _resolve_claims(session_token)
            return RedirectResponse(url=DEFAULT_NEXT_PATH, status_code=status.HTTP_303_SEE_OTHER)
        except HTTPException:
            return _login_redirect(request, clear_session=True)
    return _login_redirect(request, clear_session=False)


@router.get("/ui/login")
def ui_login(
    request: Request,
    next_path: str | None = Query(default=None, alias="next"),
    switch: bool = Query(default=False),
) -> Response:
    safe_next = _sanitize_next_path(next_path)
    if not switch:
        session_token = request.cookies.get(SESSION_COOKIE_NAME)
        if session_token:
            try:
                _ = _resolve_claims(session_token)
                return RedirectResponse(url=safe_next, status_code=status.HTTP_303_SEE_OTHER)
            except HTTPException:
                pass
    return _render_login(request, next_path=safe_next)


@router.post("/ui/login")
def ui_login_submit(
    request: Request,
    tenant_id: str = Form(...),
    username: str = Form(...),
    password: str = Form(...),
    csrf_token: str = Form(...),
    next_path: str = Form(DEFAULT_NEXT_PATH, alias="next"),
) -> Response:
    safe_next = _sanitize_next_path(next_path)
    try:
        _verify_csrf(request, csrf_token)
    except HTTPException as exc:
        return _render_login(
            request,
            next_path=safe_next,
            selected_tenant=tenant_id,
            username=username,
            error_message=str(exc.detail),
            status_code=exc.status_code,
        )

    service = IdentityService()
    try:
        user, permissions = service.dev_login(tenant_id, username, password)
    except (AuthError, NotFoundError):
        return _render_login(
            request,
            next_path=safe_next,
            selected_tenant=tenant_id,
            username=username,
            error_message="invalid tenant, username, or password",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    token = create_access_token(
        user_id=user.id,
        tenant_id=user.tenant_id,
        permissions=permissions,
    )
    response = RedirectResponse(url=safe_next, status_code=status.HTTP_303_SEE_OTHER)
    _set_session_cookie(response, token)
    _set_csrf_cookie(response, _new_csrf_token())
    return response


@router.post("/ui/logout")
def ui_logout(request: Request, csrf_token: str = Form(...)) -> RedirectResponse:
    _verify_csrf(request, csrf_token)
    response = RedirectResponse(url="/ui/login", status_code=status.HTTP_303_SEE_OTHER)
    _clear_session_cookie(response)
    _set_csrf_cookie(response, _new_csrf_token())
    return response


@router.get("/ui/console")
def ui_console(request: Request, token: str | None = Query(default=None)) -> Response:
    try:
        resolved_token, claims, from_query = _resolve_ui_access(request, token=token)
    except HTTPException:
        return _login_redirect(request, clear_session=True)

    stats = DashboardService().get_stats(claims["tenant_id"])
    return _render_console(
        request,
        template_name="ui_console.html",
        token=resolved_token,
        claims=claims,
        active_nav="console",
        title="SaaS Console",
        subtitle="Unified module workspace with RBAC-aware navigation.",
        session_from_query=from_query,
        stats=stats,
    )


@router.get("/ui/inspection")
def ui_inspection(request: Request, token: str | None = Query(default=None)) -> Any:
    try:
        resolved_token, claims, from_query = _resolve_ui_access(
            request,
            token=token,
            required_permission=PERM_INSPECTION_READ,
        )
    except HTTPException as exc:
        if exc.status_code == status.HTTP_401_UNAUTHORIZED:
            return _login_redirect(request, clear_session=True)
        raise

    service = InspectionService()
    tasks = service.list_tasks(claims["tenant_id"], viewer_user_id=claims["sub"])
    return _render_console(
        request,
        template_name="inspection_list.html",
        token=resolved_token,
        claims=claims,
        active_nav="inspection",
        title="Inspection",
        subtitle="Inspection task list and observation entry.",
        session_from_query=from_query,
        tasks=tasks,
    )


@router.get("/ui/inspection/tasks/{task_id}")
def ui_inspection_task(request: Request, task_id: str, token: str | None = Query(default=None)) -> Any:
    try:
        resolved_token, claims, from_query = _resolve_ui_access(
            request,
            token=token,
            required_permission=PERM_INSPECTION_READ,
        )
    except HTTPException as exc:
        if exc.status_code == status.HTTP_401_UNAUTHORIZED:
            return _login_redirect(request, clear_session=True)
        raise

    service = InspectionService()
    task = service.get_task(claims["tenant_id"], task_id, viewer_user_id=claims["sub"])
    observations = service.list_observations(claims["tenant_id"], task_id, viewer_user_id=claims["sub"])
    observations_json = [
        {
            "id": item.id,
            "position_lat": item.position_lat,
            "position_lon": item.position_lon,
            "severity": item.severity,
            "item_code": item.item_code,
            "note": item.note,
            "ts": item.ts.isoformat(),
        }
        for item in observations
    ]
    return _render_console(
        request,
        template_name="inspection_task_detail.html",
        token=resolved_token,
        claims=claims,
        active_nav="inspection",
        title=f"Inspection Task {task.id}",
        subtitle="Task detail, observation map and export actions.",
        session_from_query=from_query,
        task=task,
        observations=observations,
        observations_json=observations_json,
    )


@router.get("/ui/defects")
def ui_defects(request: Request, token: str | None = Query(default=None)) -> Any:
    try:
        resolved_token, claims, from_query = _resolve_ui_access(
            request,
            token=token,
            required_permission=PERM_DEFECT_READ,
        )
    except HTTPException as exc:
        if exc.status_code == status.HTTP_401_UNAUTHORIZED:
            return _login_redirect(request, clear_session=True)
        raise

    service = DefectService()
    defects = service.list_defects(claims["tenant_id"], viewer_user_id=claims["sub"])
    return _render_console(
        request,
        template_name="defects.html",
        token=resolved_token,
        claims=claims,
        active_nav="defects",
        title="Defects",
        subtitle="Defect closure workflow and quick handling.",
        session_from_query=from_query,
        defects=defects,
    )


@router.get("/ui/emergency")
def ui_emergency(request: Request, token: str | None = Query(default=None)) -> Any:
    try:
        resolved_token, claims, from_query = _resolve_ui_access(
            request,
            token=token,
            required_permission=PERM_INCIDENT_READ,
        )
    except HTTPException as exc:
        if exc.status_code == status.HTTP_401_UNAUTHORIZED:
            return _login_redirect(request, clear_session=True)
        raise

    incidents = IncidentService().list_incidents(claims["tenant_id"], viewer_user_id=claims["sub"])
    return _render_console(
        request,
        template_name="emergency.html",
        token=resolved_token,
        claims=claims,
        active_nav="emergency",
        title="Emergency",
        subtitle="Emergency response launch and incident tracking.",
        session_from_query=from_query,
        incidents=incidents,
    )


@router.get("/ui/command-center")
def ui_command_center(request: Request, token: str | None = Query(default=None)) -> Any:
    try:
        resolved_token, claims, from_query = _resolve_ui_access(
            request,
            token=token,
            required_permission=PERM_DASHBOARD_READ,
        )
    except HTTPException as exc:
        if exc.status_code == status.HTTP_401_UNAUTHORIZED:
            return _login_redirect(request, clear_session=True)
        raise

    stats = DashboardService().get_stats(claims["tenant_id"])
    return _render_console(
        request,
        template_name="command_center.html",
        token=resolved_token,
        claims=claims,
        active_nav="command-center",
        title="Command Center",
        subtitle="Realtime map situation and dashboard telemetry.",
        session_from_query=from_query,
        stats=stats,
    )


def _render_module_hub(
    request: Request,
    *,
    token: str,
    claims: dict[str, Any],
    session_from_query: bool,
    active_nav: str,
    title: str,
    subtitle: str,
    capability_points: list[str],
    api_links: list[dict[str, str]],
) -> Response:
    return _render_console(
        request,
        template_name="ui_module_hub.html",
        token=token,
        claims=claims,
        active_nav=active_nav,
        title=title,
        subtitle=subtitle,
        session_from_query=session_from_query,
        capability_points=capability_points,
        api_links=api_links,
    )


@router.get("/ui/task-center")
def ui_task_center(request: Request, token: str | None = Query(default=None)) -> Response:
    try:
        resolved_token, claims, from_query = _resolve_ui_access(
            request,
            token=token,
            required_permission=PERM_MISSION_READ,
        )
    except HTTPException as exc:
        if exc.status_code == status.HTTP_401_UNAUTHORIZED:
            return _login_redirect(request, clear_session=True)
        raise
    return _render_module_hub(
        request,
        token=resolved_token,
        claims=claims,
        session_from_query=from_query,
        active_nav="task-center",
        title="Task Center",
        subtitle="Unified task workflow operations entry.",
        capability_points=[
            "Task type/template lifecycle entry.",
            "Dispatch, approval and collaboration APIs.",
            "Task history and state transition governance.",
        ],
        api_links=[
            {"label": "List tasks", "href": "/api/task-center/tasks"},
            {"label": "List task templates", "href": "/api/task-center/templates"},
            {"label": "List task types", "href": "/api/task-center/task-types"},
        ],
    )


@router.get("/ui/assets")
def ui_assets(request: Request, token: str | None = Query(default=None)) -> Response:
    try:
        resolved_token, claims, from_query = _resolve_ui_access(
            request,
            token=token,
            required_permission=PERM_REGISTRY_READ,
        )
    except HTTPException as exc:
        if exc.status_code == status.HTTP_401_UNAUTHORIZED:
            return _login_redirect(request, clear_session=True)
        raise
    return _render_module_hub(
        request,
        token=resolved_token,
        claims=claims,
        session_from_query=from_query,
        active_nav="assets",
        title="Assets",
        subtitle="Asset and resource pool operations entry.",
        capability_points=[
            "Asset ledger and lifecycle state operations.",
            "Availability and health updates.",
            "Maintenance workorder workflows.",
        ],
        api_links=[
            {"label": "List assets", "href": "/api/assets"},
            {"label": "Asset pool", "href": "/api/assets/pool"},
            {"label": "Maintenance workorders", "href": "/api/assets/maintenance/workorders"},
        ],
    )


@router.get("/ui/compliance")
def ui_compliance(request: Request, token: str | None = Query(default=None)) -> Response:
    try:
        resolved_token, claims, from_query = _resolve_ui_access(
            request,
            token=token,
            required_permission=PERM_APPROVAL_READ,
        )
    except HTTPException as exc:
        if exc.status_code == status.HTTP_401_UNAUTHORIZED:
            return _login_redirect(request, clear_session=True)
        raise
    return _render_module_hub(
        request,
        token=resolved_token,
        claims=claims,
        session_from_query=from_query,
        active_nav="compliance",
        title="Compliance",
        subtitle="Airspace and approval compliance entry.",
        capability_points=[
            "Approval review and audit export entry.",
            "Airspace and preflight checklist APIs.",
            "Compliance decision transparency.",
        ],
        api_links=[
            {"label": "List approvals", "href": "/api/approvals"},
            {"label": "List airspace zones", "href": "/api/compliance/airspace/zones"},
            {"label": "List preflight templates", "href": "/api/compliance/preflight/templates"},
        ],
    )


@router.get("/ui/alerts")
def ui_alerts(request: Request, token: str | None = Query(default=None)) -> Response:
    try:
        resolved_token, claims, from_query = _resolve_ui_access(
            request,
            token=token,
            required_permission=PERM_ALERT_READ,
        )
    except HTTPException as exc:
        if exc.status_code == status.HTTP_401_UNAUTHORIZED:
            return _login_redirect(request, clear_session=True)
        raise
    return _render_module_hub(
        request,
        token=resolved_token,
        claims=claims,
        session_from_query=from_query,
        active_nav="alerts",
        title="Alerts",
        subtitle="Alert routing and closure entry.",
        capability_points=[
            "Alert record listing and triage entry.",
            "Routing rule and action chain visibility.",
            "Cross-module alert review linkage.",
        ],
        api_links=[
            {"label": "List alerts", "href": "/api/alert"},
            {"label": "List routing rules", "href": "/api/alert/routing-rules"},
        ],
    )


@router.get("/ui/reports")
def ui_reports(request: Request, token: str | None = Query(default=None)) -> Response:
    try:
        resolved_token, claims, from_query = _resolve_ui_access(
            request,
            token=token,
            required_permission=PERM_REPORTING_READ,
        )
    except HTTPException as exc:
        if exc.status_code == status.HTTP_401_UNAUTHORIZED:
            return _login_redirect(request, clear_session=True)
        raise
    return _render_module_hub(
        request,
        token=resolved_token,
        claims=claims,
        session_from_query=from_query,
        active_nav="reports",
        title="Reports",
        subtitle="Operational report and KPI export entry.",
        capability_points=[
            "Inspection report export entry.",
            "KPI snapshot and governance report entry.",
            "Unified outcome reporting access.",
        ],
        api_links=[
            {"label": "Inspection report export", "href": "/api/reporting/inspection/export"},
            {"label": "KPI latest snapshot", "href": "/api/kpi/snapshots/latest"},
            {"label": "Governance export", "href": "/api/kpi/governance/export"},
        ],
    )


@router.get("/ui/platform")
def ui_platform(request: Request, token: str | None = Query(default=None)) -> Response:
    try:
        resolved_token, claims, from_query = _resolve_ui_access(
            request,
            token=token,
            required_permission=PERM_IDENTITY_READ,
        )
    except HTTPException as exc:
        if exc.status_code == status.HTTP_401_UNAUTHORIZED:
            return _login_redirect(request, clear_session=True)
        raise
    return _render_module_hub(
        request,
        token=resolved_token,
        claims=claims,
        session_from_query=from_query,
        active_nav="platform",
        title="Platform Governance",
        subtitle="Tenant and RBAC governance entry.",
        capability_points=[
            "Tenant and user governance entry.",
            "Role template and permission matrix entry.",
            "Tenant export and purge governance entry.",
        ],
        api_links=[
            {"label": "List tenants", "href": "/api/identity/tenants"},
            {"label": "List users", "href": "/api/identity/users"},
            {"label": "Role templates", "href": "/api/identity/role-templates"},
            {"label": "Tenant export", "href": "/api/tenants/{tenant_id}/export"},
            {"label": "Tenant purge dry-run", "href": "/api/tenants/{tenant_id}/purge:dry_run"},
        ],
    )
