from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from secrets import compare_digest, token_urlsafe
from typing import Any
from urllib.parse import quote, urlparse

from fastapi import APIRouter, Form, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from app.domain.models import (
    AiModelVersionStatus,
    AiOutputReviewStatus,
    AiReviewActionType,
    AirspacePolicyEffect,
    AirspacePolicyLayer,
    AirspaceZoneType,
    AlertHandlingActionType,
    AlertPriority,
    AlertRouteChannel,
    AlertRouteDeliveryStatus,
    AlertStatus,
    AlertType,
    ApprovalFlowAction,
    AssetAvailabilityStatus,
    AssetHealthStatus,
    BillingCycle,
    BillingInvoiceStatus,
    BillingQuotaEnforcementMode,
    BillingSubscriptionStatus,
    MaintenanceWorkOrderStatus,
    OpenAdapterIngressStatus,
    OpenWebhookAuthType,
    OpenWebhookDeliveryStatus,
    OutcomeSourceType,
    OutcomeStatus,
    OutcomeType,
    RawDataAccessTier,
    RawDataType,
    ReportExportStatus,
    ReportFileFormat,
    Tenant,
)
from app.domain.permissions import (
    PERM_AI_READ,
    PERM_AI_WRITE,
    PERM_ALERT_READ,
    PERM_ALERT_WRITE,
    PERM_APPROVAL_READ,
    PERM_APPROVAL_WRITE,
    PERM_BILLING_READ,
    PERM_BILLING_WRITE,
    PERM_DASHBOARD_READ,
    PERM_DEFECT_READ,
    PERM_DEFECT_WRITE,
    PERM_IDENTITY_READ,
    PERM_IDENTITY_WRITE,
    PERM_INCIDENT_READ,
    PERM_INCIDENT_WRITE,
    PERM_INSPECTION_READ,
    PERM_INSPECTION_WRITE,
    PERM_MISSION_APPROVE,
    PERM_MISSION_READ,
    PERM_MISSION_WRITE,
    PERM_REGISTRY_READ,
    PERM_REGISTRY_WRITE,
    PERM_REPORTING_READ,
    PERM_REPORTING_WRITE,
    has_permission,
)
from app.domain.state_machine import TaskCenterState
from app.infra.auth import create_access_token, decode_access_token
from app.infra.db import get_engine
from app.services.ai_service import AiAssistantService
from app.services.alert_service import AlertService
from app.services.asset_maintenance_service import AssetMaintenanceService
from app.services.asset_service import AssetService
from app.services.billing_service import BillingService
from app.services.compliance_service import ComplianceService
from app.services.dashboard_service import DashboardService
from app.services.defect_service import DefectService
from app.services.identity_service import AuthError, IdentityService
from app.services.identity_service import NotFoundError as IdentityNotFoundError
from app.services.incident_service import IncidentService
from app.services.inspection_service import InspectionService
from app.services.kpi_service import KpiService
from app.services.kpi_service import NotFoundError as KpiNotFoundError
from app.services.open_platform_service import OpenPlatformService
from app.services.outcome_service import OutcomeService
from app.services.reporting_service import ReportingService
from app.services.task_center_service import TaskCenterService

router = APIRouter()
templates = Jinja2Templates(directory=str(Path("app") / "web" / "templates"))

SESSION_COOKIE_NAME = "uav_ui_session"
CSRF_COOKIE_NAME = "uav_ui_csrf"
SESSION_MAX_AGE_SECONDS = 60 * 60 * 8
DEFAULT_NEXT_PATH = "/ui/console"


@dataclass(frozen=True)
class ConsoleNavGroup:
    key: str
    label: str
    description: str


@dataclass(frozen=True)
class ConsoleNavItem:
    key: str
    group_key: str
    label: str
    href: str
    description: str
    required_permission: str | None = None


NAV_GROUPS: tuple[ConsoleNavGroup, ...] = (
    ConsoleNavGroup(
        key="overview",
        label="Overview",
        description="Cross-module entry and workspace overview.",
    ),
    ConsoleNavGroup(
        key="observe",
        label="Observe",
        description="Realtime situation and monitoring surfaces.",
    ),
    ConsoleNavGroup(
        key="execute",
        label="Execute",
        description="Operational task execution and closure workflows.",
    ),
    ConsoleNavGroup(
        key="govern",
        label="Govern",
        description="Compliance, alert and reporting governance surfaces.",
    ),
    ConsoleNavGroup(
        key="platform",
        label="Platform",
        description="Identity and tenant-level platform operations.",
    ),
)


NAV_ITEMS: tuple[ConsoleNavItem, ...] = (
    ConsoleNavItem(
        key="console",
        group_key="overview",
        label="Workbench",
        href="/ui/console",
        description="Cross-module operation workspace and entry.",
    ),
    ConsoleNavItem(
        key="command-center",
        group_key="observe",
        label="Command Center",
        href="/ui/command-center",
        description="Realtime map, stream and dashboard views.",
        required_permission=PERM_DASHBOARD_READ,
    ),
    ConsoleNavItem(
        key="inspection",
        group_key="execute",
        label="Inspection",
        href="/ui/inspection",
        description="Inspection task and observation list.",
        required_permission=PERM_INSPECTION_READ,
    ),
    ConsoleNavItem(
        key="defects",
        group_key="execute",
        label="Defects",
        href="/ui/defects",
        description="Defect closure workflow and quick actions.",
        required_permission=PERM_DEFECT_READ,
    ),
    ConsoleNavItem(
        key="emergency",
        group_key="execute",
        label="Emergency",
        href="/ui/emergency",
        description="Emergency dispatch and incident launch.",
        required_permission=PERM_INCIDENT_READ,
    ),
    ConsoleNavItem(
        key="task-center",
        group_key="execute",
        label="Task Center",
        href="/ui/task-center",
        description="Task lifecycle and workflow entry.",
        required_permission=PERM_MISSION_READ,
    ),
    ConsoleNavItem(
        key="assets",
        group_key="execute",
        label="Assets",
        href="/ui/assets",
        description="Device and asset ledger entry.",
        required_permission=PERM_REGISTRY_READ,
    ),
    ConsoleNavItem(
        key="compliance",
        group_key="govern",
        label="Compliance",
        href="/ui/compliance",
        description="Approval and compliance capability entry.",
        required_permission=PERM_APPROVAL_READ,
    ),
    ConsoleNavItem(
        key="alerts",
        group_key="govern",
        label="Alerts",
        href="/ui/alerts",
        description="Alert routing and handling entry.",
        required_permission=PERM_ALERT_READ,
    ),
    ConsoleNavItem(
        key="reports",
        group_key="govern",
        label="Reports",
        href="/ui/reports",
        description="Reporting and KPI output entry.",
        required_permission=PERM_REPORTING_READ,
    ),
    ConsoleNavItem(
        key="ai-governance",
        group_key="govern",
        label="AI Governance",
        href="/ui/ai-governance",
        description="Model version governance and evidence replay entry.",
        required_permission=PERM_AI_READ,
    ),
    ConsoleNavItem(
        key="commercial-ops",
        group_key="platform",
        label="Commercial Ops",
        href="/ui/commercial-ops",
        description="Billing, quota, tenant operations, and invoice lifecycle.",
        required_permission=PERM_BILLING_READ,
    ),
    ConsoleNavItem(
        key="open-platform",
        group_key="platform",
        label="Open Platform",
        href="/ui/open-platform",
        description="Credential, webhook, and adapter event operations.",
        required_permission=PERM_REPORTING_READ,
    ),
    ConsoleNavItem(
        key="platform",
        group_key="platform",
        label="Platform",
        href="/ui/platform",
        description="Tenant, role, and platform governance entry.",
        required_permission=PERM_IDENTITY_READ,
    ),
)


UI_VISIBILITY_MATRIX: tuple[dict[str, str | None], ...] = (
    {
        "group": "Observe",
        "page": "Command Center",
        "route": "/ui/command-center",
        "page_permission": PERM_DASHBOARD_READ,
        "write_permission": None,
        "write_actions": "Read-only operational view",
    },
    {
        "group": "Execute",
        "page": "Task Center",
        "route": "/ui/task-center",
        "page_permission": PERM_MISSION_READ,
        "write_permission": PERM_MISSION_WRITE,
        "write_actions": "Transition and dispatch quick actions",
    },
    {
        "group": "Execute",
        "page": "Assets",
        "route": "/ui/assets",
        "page_permission": PERM_REGISTRY_READ,
        "write_permission": PERM_REGISTRY_WRITE,
        "write_actions": "Availability and health updates",
    },
    {
        "group": "Govern",
        "page": "Compliance",
        "route": "/ui/compliance",
        "page_permission": PERM_APPROVAL_READ,
        "write_permission": PERM_APPROVAL_WRITE,
        "write_actions": "Approval and policy governance actions",
    },
    {
        "group": "Govern",
        "page": "Alerts",
        "route": "/ui/alerts",
        "page_permission": PERM_ALERT_READ,
        "write_permission": PERM_ALERT_WRITE,
        "write_actions": "Ack and close actions",
    },
    {
        "group": "Govern",
        "page": "Reports",
        "route": "/ui/reports",
        "page_permission": PERM_REPORTING_READ,
        "write_permission": PERM_REPORTING_WRITE,
        "write_actions": "Report export and governance actions",
    },
    {
        "group": "Govern",
        "page": "AI Governance",
        "route": "/ui/ai-governance",
        "page_permission": PERM_AI_READ,
        "write_permission": PERM_AI_WRITE,
        "write_actions": "Model version governance and review actions",
    },
    {
        "group": "Platform",
        "page": "Commercial Ops",
        "route": "/ui/commercial-ops",
        "page_permission": PERM_BILLING_READ,
        "write_permission": PERM_BILLING_WRITE,
        "write_actions": "Billing plan/subscription/quota and invoice actions",
    },
    {
        "group": "Platform",
        "page": "Open Platform",
        "route": "/ui/open-platform",
        "page_permission": PERM_REPORTING_READ,
        "write_permission": PERM_REPORTING_WRITE,
        "write_actions": "Credential/webhook and adapter ingest actions",
    },
    {
        "group": "Platform",
        "page": "Platform Governance",
        "route": "/ui/platform",
        "page_permission": PERM_IDENTITY_READ,
        "write_permission": PERM_IDENTITY_WRITE,
        "write_actions": "Identity and role governance actions",
    },
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
    return token_urlsafe(24)


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
    if not compare_digest(csrf_cookie, csrf_token):
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
    required_any_permissions: tuple[str, ...] | None = None,
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
    if required_any_permissions and not any(has_permission(claims, item) for item in required_any_permissions):
        joined = " | ".join(required_any_permissions)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"missing permission (any): {joined}")
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
                "group_key": item.group_key,
                "label": item.label,
                "href": item.href,
                "description": item.description,
                "active": item.key == active_key,
            }
        )
    return rows


def _grouped_nav_items(nav_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped_map: dict[str, dict[str, Any]] = {
        group.key: {
            "key": group.key,
            "label": group.label,
            "description": group.description,
            "items": [],
        }
        for group in NAV_GROUPS
    }
    for item in nav_rows:
        group_key = str(item.get("group_key", ""))
        row = grouped_map.get(group_key)
        if row is None:
            continue
        row["items"].append(item)
    return [grouped_map[group.key] for group in NAV_GROUPS if grouped_map[group.key]["items"]]


def _resolved_ui_visibility_matrix(claims: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in UI_VISIBILITY_MATRIX:
        page_permission = item["page_permission"]
        write_permission = item["write_permission"]
        can_view = page_permission is None or has_permission(claims, page_permission)
        can_write = write_permission is None or has_permission(claims, write_permission)
        rows.append(
            {
                "group": item["group"],
                "page": item["page"],
                "route": item["route"],
                "page_permission": page_permission or "-",
                "write_permission": write_permission or "-",
                "write_actions": item["write_actions"],
                "can_view": can_view,
                "can_write": can_write,
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
    nav_groups = _grouped_nav_items(nav_rows)
    module_entries = [item for item in nav_rows if item["key"] != "console"]
    module_entry_groups = _grouped_nav_items(module_entries)

    active_item = next((item for item in nav_rows if item["active"]), None)
    active_label = active_item["label"] if active_item else "Workbench"
    active_group = next((group for group in nav_groups if any(item["active"] for item in group["items"])), None)
    active_group_label = active_group["label"] if active_group else "Overview"

    breadcrumbs = ["Console", active_group_label]
    if active_label != active_group_label:
        breadcrumbs.append(active_label)

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
        "nav_groups": nav_groups,
        "module_entries": module_entries,
        "module_entry_groups": module_entry_groups,
        "breadcrumbs": breadcrumbs,
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
    except (AuthError, IdentityNotFoundError):
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
    templates = service.list_templates(claims["tenant_id"])
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
        templates=templates,
        can_inspection_write=has_permission(claims, PERM_INSPECTION_WRITE),
        can_defect_write=has_permission(claims, PERM_DEFECT_WRITE),
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
        can_inspection_write=has_permission(claims, PERM_INSPECTION_WRITE),
        can_defect_write=has_permission(claims, PERM_DEFECT_WRITE),
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
        can_defect_write=has_permission(claims, PERM_DEFECT_WRITE),
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
        can_incident_write=has_permission(claims, PERM_INCIDENT_WRITE),
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


@router.get("/ui/task-center")
def ui_task_center(
    request: Request,
    token: str | None = Query(default=None),
    state: TaskCenterState | None = None,
) -> Response:
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

    service = TaskCenterService()
    tasks = service.list_tasks(claims["tenant_id"], state=state, viewer_user_id=claims["sub"])
    templates = service.list_templates(claims["tenant_id"], is_active=None)
    task_types = service.list_task_types(claims["tenant_id"], is_active=None)
    state_counter = Counter([item.state.value for item in tasks])

    return _render_console(
        request,
        template_name="ui_task_center.html",
        token=resolved_token,
        claims=claims,
        active_nav="task-center",
        title="Task Center",
        subtitle="Plan, dispatch and transition task workflows through a single operational queue.",
        session_from_query=from_query,
        tasks=tasks,
        task_types=task_types,
        templates=templates,
        task_state_counts=state_counter,
        task_state_options=[state.value for state in TaskCenterState],
        selected_task_state=state.value if state else "",
        can_task_write=has_permission(claims, PERM_MISSION_WRITE),
        can_task_approve=has_permission(claims, PERM_MISSION_APPROVE),
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

    service = AssetService()
    maintenance_service = AssetMaintenanceService()
    assets = service.list_assets(claims["tenant_id"], viewer_user_id=claims["sub"])
    pool_summary = service.summarize_resource_pool(claims["tenant_id"], viewer_user_id=claims["sub"])
    maintenance_workorders = maintenance_service.list_workorders(claims["tenant_id"])

    available_count = len([item for item in assets if item.availability_status == AssetAvailabilityStatus.AVAILABLE])
    healthy_count = len([item for item in assets if item.health_status == AssetHealthStatus.HEALTHY])
    region_count = len({item.region_code or "UNASSIGNED" for item in assets})

    return _render_console(
        request,
        template_name="ui_assets.html",
        token=resolved_token,
        claims=claims,
        active_nav="assets",
        title="Assets",
        subtitle="Operate asset inventory, pool capacity, and health status from one page.",
        session_from_query=from_query,
        assets=assets,
        pool_summary=pool_summary,
        available_count=available_count,
        healthy_count=healthy_count,
        region_count=region_count,
        maintenance_workorders=maintenance_workorders,
        availability_options=[item.value for item in AssetAvailabilityStatus],
        health_options=[item.value for item in AssetHealthStatus],
        maintenance_status_options=[item.value for item in MaintenanceWorkOrderStatus],
        can_asset_write=has_permission(claims, PERM_REGISTRY_WRITE),
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

    service = ComplianceService()
    approvals = service.list_approvals(claims["tenant_id"])
    can_mission_read = has_permission(claims, PERM_MISSION_READ)
    zones = service.list_airspace_zones(claims["tenant_id"]) if can_mission_read else []
    preflight_templates = service.list_preflight_templates(claims["tenant_id"]) if can_mission_read else []
    decision_records = service.list_decision_records(claims["tenant_id"]) if can_mission_read else []

    return _render_console(
        request,
        template_name="ui_compliance.html",
        token=resolved_token,
        claims=claims,
        active_nav="compliance",
        title="Compliance",
        subtitle="Track approvals, airspace controls, and decision evidence for audit readiness.",
        session_from_query=from_query,
        approvals=approvals,
        zones=zones,
        preflight_templates=preflight_templates,
        decision_records=decision_records,
        can_mission_read=can_mission_read,
        can_mission_write=has_permission(claims, PERM_MISSION_WRITE),
        can_approval_write=has_permission(claims, PERM_APPROVAL_WRITE),
        zone_type_options=[item.value for item in AirspaceZoneType],
        zone_layer_options=[item.value for item in AirspacePolicyLayer],
        zone_effect_options=[item.value for item in AirspacePolicyEffect],
        approval_flow_action_options=[item.value for item in ApprovalFlowAction],
    )


@router.get("/ui/alerts")
def ui_alerts(
    request: Request,
    token: str | None = Query(default=None),
    alert_status: AlertStatus | None = None,
    drone_id: str | None = None,
) -> Response:
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

    service = AlertService()
    alerts = service.list_alerts(claims["tenant_id"], drone_id=drone_id, status=alert_status)
    routing_rules = service.list_routing_rules(claims["tenant_id"], is_active=None)
    oncall_shifts = service.list_oncall_shifts(claims["tenant_id"], is_active=None)
    escalation_policies = service.list_escalation_policies(claims["tenant_id"], is_active=None)
    silence_rules = service.list_silence_rules(claims["tenant_id"], is_active=None)
    aggregation_rules = service.list_aggregation_rules(claims["tenant_id"], is_active=None)
    status_counter = Counter([item.status.value for item in alerts])

    return _render_console(
        request,
        template_name="ui_alerts.html",
        token=resolved_token,
        claims=claims,
        active_nav="alerts",
        title="Alerts",
        subtitle="Handle alert triage, oncall scheduling, and escalation governance in one place.",
        session_from_query=from_query,
        alerts=alerts,
        routing_rules=routing_rules,
        oncall_shifts=oncall_shifts,
        escalation_policies=escalation_policies,
        silence_rules=silence_rules,
        aggregation_rules=aggregation_rules,
        alert_status_counts=status_counter,
        alert_status_options=[item.value for item in AlertStatus],
        alert_priority_options=[item.value for item in AlertPriority],
        alert_type_options=[item.value for item in AlertType],
        alert_channel_options=[item.value for item in AlertRouteChannel],
        alert_delivery_status_options=[item.value for item in AlertRouteDeliveryStatus],
        alert_action_type_options=[item.value for item in AlertHandlingActionType],
        selected_alert_status=alert_status.value if alert_status is not None else "",
        selected_alert_drone=drone_id or "",
        can_alert_write=has_permission(claims, PERM_ALERT_WRITE),
    )


@router.get("/ui/reports")
def ui_reports(request: Request, token: str | None = Query(default=None)) -> Response:
    try:
        resolved_token, claims, from_query = _resolve_ui_access(
            request,
            token=token,
            required_any_permissions=(PERM_REPORTING_READ, PERM_INSPECTION_READ, PERM_AI_READ),
        )
    except HTTPException as exc:
        if exc.status_code == status.HTTP_401_UNAUTHORIZED:
            return _login_redirect(request, clear_session=True)
        raise

    can_reporting_read = has_permission(claims, PERM_REPORTING_READ)
    can_reporting_write = has_permission(claims, PERM_REPORTING_WRITE)
    can_inspection_read = has_permission(claims, PERM_INSPECTION_READ)
    can_inspection_write = has_permission(claims, PERM_INSPECTION_WRITE)
    can_ai_read = has_permission(claims, PERM_AI_READ)
    can_ai_write = has_permission(claims, PERM_AI_WRITE)

    overview: dict[str, int | float] = {
        "missions_total": 0,
        "inspections_total": 0,
        "defects_total": 0,
        "defects_closed": 0,
        "closure_rate": 0.0,
    }
    closure_rate: dict[str, int | float] = {"total": 0, "closed": 0, "closure_rate": 0.0}
    device_utilization: list[Any] = []
    outcome_templates: list[Any] = []
    outcome_exports: list[Any] = []
    snapshots: list[Any] = []
    latest_snapshot: Any = None
    raw_records: list[Any] = []
    outcome_records: list[Any] = []

    if can_reporting_read:
        reporting_service = ReportingService()
        kpi_service = KpiService()
        overview = reporting_service.overview(claims["tenant_id"], viewer_user_id=claims["sub"]).model_dump()
        closure_rate = reporting_service.closure_rate(claims["tenant_id"], viewer_user_id=claims["sub"]).model_dump()
        device_utilization = reporting_service.device_utilization(claims["tenant_id"], viewer_user_id=claims["sub"])
        outcome_templates = reporting_service.list_outcome_report_templates(claims["tenant_id"])
        outcome_exports = reporting_service.list_outcome_report_exports(claims["tenant_id"], limit=20)
        snapshots = kpi_service.list_snapshots(claims["tenant_id"])[:8]
        try:
            latest_snapshot = kpi_service.get_latest_snapshot(claims["tenant_id"])
        except KpiNotFoundError:
            latest_snapshot = None

    if can_inspection_read:
        outcome_service = OutcomeService()
        raw_records = outcome_service.list_raw_records(claims["tenant_id"], viewer_user_id=claims["sub"])
        outcome_records = outcome_service.list_outcome_records(claims["tenant_id"], viewer_user_id=claims["sub"])

    return _render_console(
        request,
        template_name="ui_reports.html",
        token=resolved_token,
        claims=claims,
        active_nav="reports",
        title="Reports",
        subtitle="Review KPI snapshots, closure performance, and report assets for governance output.",
        session_from_query=from_query,
        overview=overview,
        closure_rate=closure_rate,
        device_utilization=device_utilization,
        raw_records=raw_records,
        outcome_records=outcome_records,
        outcome_templates=outcome_templates,
        outcome_exports=outcome_exports,
        snapshots=snapshots,
        latest_snapshot=latest_snapshot,
        can_reporting_read=can_reporting_read,
        can_reporting_write=can_reporting_write,
        can_inspection_read=can_inspection_read,
        can_inspection_write=can_inspection_write,
        can_ai_read=can_ai_read,
        can_ai_write=can_ai_write,
        raw_data_type_options=[item.value for item in RawDataType],
        raw_access_tier_options=[item.value for item in RawDataAccessTier],
        outcome_source_options=[item.value for item in OutcomeSourceType],
        outcome_type_options=[item.value for item in OutcomeType],
        outcome_status_options=[item.value for item in OutcomeStatus],
        report_format_options=[item.value for item in ReportFileFormat],
        report_export_status_options=[item.value for item in ReportExportStatus],
    )


@router.get("/ui/ai-governance")
def ui_ai_governance(request: Request, token: str | None = Query(default=None)) -> Response:
    try:
        resolved_token, claims, from_query = _resolve_ui_access(
            request,
            token=token,
            required_any_permissions=(PERM_AI_READ, PERM_REPORTING_READ),
        )
    except HTTPException as exc:
        if exc.status_code == status.HTTP_401_UNAUTHORIZED:
            return _login_redirect(request, clear_session=True)
        raise

    can_ai_data_read = has_permission(claims, PERM_AI_READ) or has_permission(claims, PERM_REPORTING_READ)
    can_ai_data_write = has_permission(claims, PERM_AI_WRITE) or has_permission(claims, PERM_REPORTING_WRITE)

    model_catalogs: list[Any] = []
    jobs: list[Any] = []
    outputs: list[Any] = []
    if can_ai_data_read:
        service = AiAssistantService()
        model_catalogs = service.list_model_catalogs(claims["tenant_id"])
        jobs = service.list_jobs(claims["tenant_id"], viewer_user_id=claims["sub"])
        outputs = service.list_outputs(claims["tenant_id"], viewer_user_id=claims["sub"])

    return _render_console(
        request,
        template_name="ui_ai_governance.html",
        token=resolved_token,
        claims=claims,
        active_nav="ai-governance",
        title="AI Governance",
        subtitle="Operate model versions, rollout policies, evaluation compare, and evidence-chain review.",
        session_from_query=from_query,
        model_catalogs=model_catalogs,
        jobs=jobs,
        outputs=outputs,
        can_ai_data_read=can_ai_data_read,
        can_ai_data_write=can_ai_data_write,
        ai_version_status_options=[item.value for item in AiModelVersionStatus],
        ai_output_review_status_options=[item.value for item in AiOutputReviewStatus],
        ai_review_action_options=[item.value for item in AiReviewActionType],
    )


@router.get("/ui/commercial-ops")
def ui_commercial_ops(request: Request, token: str | None = Query(default=None)) -> Response:
    try:
        resolved_token, claims, from_query = _resolve_ui_access(
            request,
            token=token,
            required_permission=PERM_BILLING_READ,
        )
    except HTTPException as exc:
        if exc.status_code == status.HTTP_401_UNAUTHORIZED:
            return _login_redirect(request, clear_session=True)
        raise

    can_billing_write = has_permission(claims, PERM_BILLING_WRITE)
    can_identity_read = has_permission(claims, PERM_IDENTITY_READ)

    billing_service = BillingService()
    plans = billing_service.list_plans(claims["tenant_id"])
    subscriptions = billing_service.list_subscriptions(claims["tenant_id"])
    quota_overrides = billing_service.list_quota_overrides(claims["tenant_id"])
    quota_snapshot = billing_service.get_effective_quotas(claims["tenant_id"])
    usage_summary = billing_service.list_usage_summary(claims["tenant_id"])
    invoices = billing_service.list_invoices(claims["tenant_id"])

    users: list[Any] = []
    roles: list[Any] = []
    org_units: list[Any] = []
    if can_identity_read:
        identity_service = IdentityService()
        users = identity_service.list_users(claims["tenant_id"])
        roles = identity_service.list_roles(claims["tenant_id"])
        org_units = identity_service.list_org_units(claims["tenant_id"])

    return _render_console(
        request,
        template_name="ui_commercial_ops.html",
        token=resolved_token,
        claims=claims,
        active_nav="commercial-ops",
        title="Commercial Ops",
        subtitle="Operate billing lifecycle, quota governance, and tenant operations visibility.",
        session_from_query=from_query,
        plans=plans,
        subscriptions=subscriptions,
        quota_overrides=quota_overrides,
        quota_snapshot=quota_snapshot,
        usage_summary=usage_summary,
        invoices=invoices,
        users=users,
        roles=roles,
        org_units=org_units,
        can_billing_write=can_billing_write,
        can_identity_read=can_identity_read,
        billing_cycle_options=[item.value for item in BillingCycle],
        billing_subscription_status_options=[item.value for item in BillingSubscriptionStatus],
        billing_quota_mode_options=[item.value for item in BillingQuotaEnforcementMode],
        billing_invoice_status_options=[item.value for item in BillingInvoiceStatus],
    )


@router.get("/ui/open-platform")
def ui_open_platform(request: Request, token: str | None = Query(default=None)) -> Response:
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

    can_open_platform_write = has_permission(claims, PERM_REPORTING_WRITE)
    service = OpenPlatformService()
    credentials = service.list_credentials(claims["tenant_id"])
    webhooks = service.list_webhooks(claims["tenant_id"])
    adapter_events = service.list_adapter_events(claims["tenant_id"])

    return _render_console(
        request,
        template_name="ui_open_platform.html",
        token=resolved_token,
        claims=claims,
        active_nav="open-platform",
        title="Open Platform",
        subtitle="Manage external credentials, webhook delivery, and adapter ingress events.",
        session_from_query=from_query,
        credentials=credentials,
        webhooks=webhooks,
        adapter_events=adapter_events,
        can_open_platform_write=can_open_platform_write,
        open_webhook_auth_options=[item.value for item in OpenWebhookAuthType],
        open_webhook_delivery_status_options=[item.value for item in OpenWebhookDeliveryStatus],
        open_adapter_status_options=[item.value for item in OpenAdapterIngressStatus],
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

    service = IdentityService()
    tenants = service.list_tenants(claims["tenant_id"])
    users = service.list_users(claims["tenant_id"])
    roles = service.list_roles(claims["tenant_id"])
    org_units = service.list_org_units(claims["tenant_id"])
    role_templates = service.list_role_templates()

    return _render_console(
        request,
        template_name="ui_platform.html",
        token=resolved_token,
        claims=claims,
        active_nav="platform",
        title="Platform Governance",
        subtitle="Inspect tenant identity topology, roles, and organization structure.",
        session_from_query=from_query,
        tenants=tenants,
        users=users,
        roles=roles,
        org_units=org_units,
        role_templates=role_templates,
        visibility_matrix=_resolved_ui_visibility_matrix(claims),
        can_identity_write=has_permission(claims, PERM_IDENTITY_WRITE),
    )
