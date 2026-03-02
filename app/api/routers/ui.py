from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from secrets import compare_digest, token_urlsafe
from typing import Any, NotRequired, TypedDict
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
    CapacityDecision,
    CapacityPolicyRead,
    MaintenanceWorkOrderStatus,
    ObservabilityAlertSeverity,
    ObservabilityAlertStatus,
    ObservabilityOverviewRead,
    ObservabilitySignalLevel,
    ObservabilitySignalType,
    ObservabilitySloOverviewRead,
    ObservabilitySloStatus,
    OpenAdapterIngressStatus,
    OpenWebhookAuthType,
    OpenWebhookDeliveryStatus,
    OrgUnitType,
    OutcomeSourceType,
    OutcomeStatus,
    OutcomeType,
    RawDataAccessTier,
    RawDataType,
    ReliabilityBackupRunType,
    ReliabilityRestoreDrillRead,
    ReportExportStatus,
    ReportFileFormat,
    SecurityInspectionCheckStatus,
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
    PERM_OBSERVABILITY_READ,
    PERM_OBSERVABILITY_WRITE,
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
from app.services.observability_service import ObservabilityService
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
    primary_nav: bool = True


@dataclass(frozen=True)
class RoleWorkbenchDefinition:
    key: str
    label: str
    audience: str
    summary: str
    badge: str
    required_any_permissions: tuple[str, ...]
    module_keys: tuple[str, ...]
    daily_focus: tuple[str, ...]
    risk_watch: tuple[str, ...]


NAV_GROUPS: tuple[ConsoleNavGroup, ...] = (
    ConsoleNavGroup(
        key="overview",
        label="总览",
        description="角色入口与跨模块工作总览。",
    ),
    ConsoleNavGroup(
        key="observe",
        label="态势",
        description="实时态势、地图和值守观察入口。",
    ),
    ConsoleNavGroup(
        key="execute",
        label="执行",
        description="任务执行、巡检处置与闭环流程。",
    ),
    ConsoleNavGroup(
        key="govern",
        label="治理",
        description="合规、告警、报表与审计治理入口。",
    ),
    ConsoleNavGroup(
        key="platform",
        label="平台",
        description="租户、身份与平台级治理入口。",
    ),
)


ROLE_WORKBENCHES: tuple[RoleWorkbenchDefinition, ...] = (
    RoleWorkbenchDefinition(
        key="commander",
        label="指挥工作台",
        audience="值班指挥员",
        summary="聚焦当前态势、实时告警与跨模块协同, 适合值班总览和快速决策。",
        badge="态势优先",
        required_any_permissions=(PERM_DASHBOARD_READ, PERM_ALERT_READ, PERM_REPORTING_READ),
        module_keys=("command-center", "alerts", "reports"),
        daily_focus=(
            "先查看指挥中心态势, 再确认实时告警是否需要升级。",
            "对异常任务快速分派, 保持跨班次信息一致。",
            "值班结束前导出关键指标, 确保可追溯。",
        ),
        risk_watch=(
            "实时告警积压会直接影响响应时效。",
            "地图态势与处置记录不一致时, 需要立即复核。",
        ),
    ),
    RoleWorkbenchDefinition(
        key="dispatcher",
        label="调度工作台",
        audience="调度员",
        summary="围绕任务、巡检与应急派发组织高频操作, 减少页面切换。",
        badge="任务驱动",
        required_any_permissions=(PERM_MISSION_READ, PERM_INSPECTION_READ, PERM_INCIDENT_READ),
        module_keys=("task-center", "inspection", "emergency", "assets"),
        daily_focus=(
            "优先处理今日待执行任务和待确认派单。",
            "从任务与设备入口完成派发, 不依赖手动记忆对象标识。",
            "异常工单升级前先核对资源和现场可用性。",
        ),
        risk_watch=(
            "任务超时和设备离线会放大调度拥塞。",
            "派单前未核对资产可用性时, 容易产生返工。",
        ),
    ),
    RoleWorkbenchDefinition(
        key="operator",
        label="现场执行工作台",
        audience="飞手 / 值守人员",
        summary="只保留现场高频入口, 帮助一线人员快速接单、执行和回传。",
        badge="低负担",
        required_any_permissions=(PERM_INSPECTION_READ, PERM_DEFECT_READ, PERM_REGISTRY_READ),
        module_keys=("inspection", "defects", "assets"),
        daily_focus=(
            "先确认当前待执行巡检, 再进入缺陷闭环。",
            "以对象列表选择任务和设备, 减少手工输入。",
            "遇到异常先上报, 再补充结果和说明。",
        ),
        risk_watch=(
            "现场待办过多时, 应避免同时切换多个流程。",
            "设备健康状态异常时, 不应继续执行高风险任务。",
        ),
    ),
    RoleWorkbenchDefinition(
        key="compliance",
        label="合规工作台",
        audience="审核员 / 合规员",
        summary="集中处理审批、告警和报表, 保持决策留痕与审计一致。",
        badge="留痕优先",
        required_any_permissions=(PERM_APPROVAL_READ, PERM_REPORTING_READ, PERM_ALERT_READ, PERM_AI_READ),
        module_keys=("compliance", "alerts", "reports"),
        daily_focus=(
            "先处理待审批事项, 再检查告警闭环状态。",
            "重点查看证据、审批结论和导出结果是否一致。",
            "对高风险事项保留复核说明, 减少后续追问成本。",
        ),
        risk_watch=(
            "审批滞留会延长任务闭环周期。",
            "导出报表与原始记录不一致时, 应暂停对外发送。",
        ),
    ),
    RoleWorkbenchDefinition(
        key="executive",
        label="领导视图",
        audience="领导 / 只读查看者",
        summary="提供更少但更清晰的入口, 专注看全局态势、重点风险和结果输出。",
        badge="只读总览",
        required_any_permissions=(PERM_DASHBOARD_READ, PERM_REPORTING_READ),
        module_keys=("command-center", "reports"),
        daily_focus=(
            "先看当前态势, 再看日报和周报输出。",
            "关注风险与进展, 不进入细碎执行页面。",
            "需要追问时, 直接回到指挥或调度席位复核。",
        ),
        risk_watch=(
            "指标趋势异常但无人跟进时, 说明协同链路需要加压。",
            "领导视图不承载写操作, 避免误触业务动作。",
        ),
    ),
)


NAV_ITEMS: tuple[ConsoleNavItem, ...] = (
    ConsoleNavItem(
        key="console",
        group_key="overview",
        label="工作台",
        href="/ui/console",
        description="按角色进入常用业务入口。",
    ),
    ConsoleNavItem(
        key="command-center",
        group_key="observe",
        label="指挥中心",
        href="/ui/command-center",
        description="查看实时地图、轨迹与态势看板。",
        required_permission=PERM_DASHBOARD_READ,
    ),
    ConsoleNavItem(
        key="observability",
        group_key="observe",
        label="可观测性",
        href="/ui/observability",
        description="信号、SLO 与值守观测能力。",
        required_permission=PERM_OBSERVABILITY_READ,
        primary_nav=False,
    ),
    ConsoleNavItem(
        key="reliability",
        group_key="observe",
        label="可靠性",
        href="/ui/reliability",
        description="备份演练、安全巡检与容量运行手册。",
        required_permission=PERM_OBSERVABILITY_READ,
        primary_nav=False,
    ),
    ConsoleNavItem(
        key="inspection",
        group_key="execute",
        label="巡检任务",
        href="/ui/inspection",
        description="管理巡检任务和现场观察记录。",
        required_permission=PERM_INSPECTION_READ,
    ),
    ConsoleNavItem(
        key="defects",
        group_key="execute",
        label="缺陷闭环",
        href="/ui/defects",
        description="跟踪缺陷处理、分派和闭环状态。",
        required_permission=PERM_DEFECT_READ,
    ),
    ConsoleNavItem(
        key="emergency",
        group_key="execute",
        label="应急处置",
        href="/ui/emergency",
        description="发起应急任务与事件响应。",
        required_permission=PERM_INCIDENT_READ,
    ),
    ConsoleNavItem(
        key="task-center",
        group_key="execute",
        label="任务中心",
        href="/ui/task-center",
        description="统一处理任务流转、派发和审批。",
        required_permission=PERM_MISSION_READ,
    ),
    ConsoleNavItem(
        key="assets",
        group_key="execute",
        label="资产台账",
        href="/ui/assets",
        description="查看设备、资产池和健康状态。",
        required_permission=PERM_REGISTRY_READ,
    ),
    ConsoleNavItem(
        key="compliance",
        group_key="govern",
        label="合规治理",
        href="/ui/compliance",
        description="处理审批、空域与合规留痕。",
        required_permission=PERM_APPROVAL_READ,
    ),
    ConsoleNavItem(
        key="alerts",
        group_key="govern",
        label="告警中心",
        href="/ui/alerts",
        description="查看告警队列与值守处理动作。",
        required_permission=PERM_ALERT_READ,
    ),
    ConsoleNavItem(
        key="reports",
        group_key="govern",
        label="报表中心",
        href="/ui/reports",
        description="查看成果输出、指标与报告导出。",
        required_permission=PERM_REPORTING_READ,
    ),
    ConsoleNavItem(
        key="ai-governance",
        group_key="govern",
        label="AI 治理",
        href="/ui/ai-governance",
        description="模型版本治理与证据回放。",
        required_permission=PERM_AI_READ,
        primary_nav=False,
    ),
    ConsoleNavItem(
        key="commercial-ops",
        group_key="platform",
        label="商业运营",
        href="/ui/commercial-ops",
        description="计费、配额、租户运营与发票流程。",
        required_permission=PERM_BILLING_READ,
        primary_nav=False,
    ),
    ConsoleNavItem(
        key="open-platform",
        group_key="platform",
        label="开放平台",
        href="/ui/open-platform",
        description="外部凭证、Webhook 与适配器接入。",
        required_permission=PERM_REPORTING_READ,
        primary_nav=False,
    ),
    ConsoleNavItem(
        key="platform",
        group_key="platform",
        label="平台治理",
        href="/ui/platform",
        description="查看租户、角色和权限治理。",
        required_permission=PERM_IDENTITY_READ,
    ),
)


class UiVisibilityMatrixItem(TypedDict):
    group: str
    page: str
    route: str
    page_permission: str | None
    write_permission: str | None
    write_actions: str
    primary_nav: NotRequired[bool]


UI_VISIBILITY_MATRIX: tuple[UiVisibilityMatrixItem, ...] = (
    {
        "group": "Observe",
        "page": "Command Center",
        "route": "/ui/command-center",
        "page_permission": PERM_DASHBOARD_READ,
        "write_permission": None,
        "write_actions": "Read-only operational view",
    },
    {
        "group": "Observe",
        "page": "Observability",
        "route": "/ui/observability",
        "page_permission": PERM_OBSERVABILITY_READ,
        "write_permission": PERM_OBSERVABILITY_WRITE,
        "write_actions": "Signal ingest and SLO policy/evaluation actions",
        "primary_nav": False,
    },
    {
        "group": "Observe",
        "page": "Reliability",
        "route": "/ui/reliability",
        "page_permission": PERM_OBSERVABILITY_READ,
        "write_permission": PERM_OBSERVABILITY_WRITE,
        "write_actions": "Backup, restore drill, inspection, and capacity actions",
        "primary_nav": False,
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
        "primary_nav": False,
    },
    {
        "group": "Platform",
        "page": "Commercial Ops",
        "route": "/ui/commercial-ops",
        "page_permission": PERM_BILLING_READ,
        "write_permission": PERM_BILLING_WRITE,
        "write_actions": "Billing plan/subscription/quota and invoice actions",
        "primary_nav": False,
    },
    {
        "group": "Platform",
        "page": "Open Platform",
        "route": "/ui/open-platform",
        "page_permission": PERM_REPORTING_READ,
        "write_permission": PERM_REPORTING_WRITE,
        "write_actions": "Credential/webhook and adapter ingest actions",
        "primary_nav": False,
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


def _find_nav_item(key: str) -> ConsoleNavItem | None:
    return next((item for item in NAV_ITEMS if item.key == key), None)


def _find_role_workbench(key: str) -> RoleWorkbenchDefinition | None:
    return next((item for item in ROLE_WORKBENCHES if item.key == key), None)


def _is_role_workbench_visible(claims: dict[str, Any], item: RoleWorkbenchDefinition) -> bool:
    return any(has_permission(claims, permission) for permission in item.required_any_permissions)


def _nav_entry_from_key(claims: dict[str, Any], key: str) -> dict[str, str] | None:
    item = _find_nav_item(key)
    if item is None or not _is_nav_visible(claims, item):
        return None
    return {
        "key": item.key,
        "label": item.label,
        "href": item.href,
        "description": item.description,
    }


def _role_workbench_modules(claims: dict[str, Any], item: RoleWorkbenchDefinition) -> list[dict[str, str]]:
    return [
        entry
        for entry in (_nav_entry_from_key(claims, key) for key in item.module_keys)
        if entry is not None
    ]


def _visible_role_workbenches(claims: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in ROLE_WORKBENCHES:
        if not _is_role_workbench_visible(claims, item):
            continue
        module_entries = _role_workbench_modules(claims, item)
        if not module_entries:
            continue
        rows.append(
            {
                "key": item.key,
                "label": item.label,
                "audience": item.audience,
                "summary": item.summary,
                "badge": item.badge,
                "href": f"/ui/workbench/{item.key}",
                "module_entries": module_entries,
                "daily_focus": list(item.daily_focus),
                "risk_watch": list(item.risk_watch),
            }
        )
    return rows


def _console_attention_items(stats: Any) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    if stats.realtime_alerts > 0:
        items.append(
            {
                "tone": "danger",
                "title": "实时告警待处理",
                "detail": f"当前有 {stats.realtime_alerts} 条实时告警, 建议优先进入指挥或告警页面确认处置状态。",
            }
        )
    else:
        items.append(
            {
                "tone": "success",
                "title": "当前无实时告警积压",
                "detail": "可以把注意力放在任务推进和日终复盘上。",
            }
        )

    if stats.defects_total > 0:
        items.append(
            {
                "tone": "warn",
                "title": "缺陷闭环需要跟进",
                "detail": f"当前累计 {stats.defects_total} 条缺陷记录, 请确认是否存在超时未关闭项。",
            }
        )
    else:
        items.append(
            {
                "tone": "success",
                "title": "缺陷池保持清爽",
                "detail": "当前没有积压缺陷, 适合推进预防性巡检。",
            }
        )

    if stats.online_devices == 0:
        items.append(
            {
                "tone": "danger",
                "title": "在线设备为 0",
                "detail": "如果当前处于值班时段, 请先核对设备连通性和租户初始化状态。",
            }
        )
    else:
        items.append(
            {
                "tone": "success",
                "title": "设备在线状态正常",
                "detail": f"当前有 {stats.online_devices} 台在线设备, 可支持当班调度。",
            }
        )
    return items


def _workbench_next_steps(role_workbench: dict[str, Any] | None) -> list[dict[str, str]]:
    if role_workbench is None:
        return [
            {
                "title": "补充角色权限",
                "detail": "当前账号没有命中任何角色工作台, 请先在平台治理中分配对应读权限。",
            }
        ]

    steps: list[dict[str, str]] = []
    for entry in role_workbench["module_entries"][:3]:
        steps.append(
            {
                "title": f"进入 {entry['label']}",
                "detail": entry["description"],
            }
        )
    return steps


def _visible_nav_items(claims: dict[str, Any], active_key: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in NAV_ITEMS:
        if not item.primary_nav:
            continue
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


def _visible_secondary_nav_items(claims: dict[str, Any], active_key: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in NAV_ITEMS:
        if item.primary_nav:
            continue
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
        if item.get("primary_nav", True) is False:
            continue
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
    secondary_nav_rows = _visible_secondary_nav_items(claims, active_nav)
    secondary_nav_groups = _grouped_nav_items(secondary_nav_rows)
    module_entries = [item for item in nav_rows if item["key"] != "console"]
    module_entry_groups = _grouped_nav_items(module_entries)
    role_workbenches = _visible_role_workbenches(claims)

    active_visible_item = next((item for item in nav_rows if item["active"]), None)
    active_item_def = _find_nav_item(active_nav)
    active_label = active_visible_item["label"] if active_visible_item else (
        active_item_def.label if active_item_def is not None else "工作台"
    )
    active_group = next((group for group in nav_groups if any(item["active"] for item in group["items"])), None)
    active_group_label = active_group["label"] if active_group else (
        next((group.label for group in NAV_GROUPS if active_item_def is not None and group.key == active_item_def.group_key), "总览")
    )

    breadcrumbs = ["工作台", active_group_label]
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
        "secondary_nav_items": secondary_nav_rows,
        "secondary_nav_groups": secondary_nav_groups,
        "module_entries": module_entries,
        "module_entry_groups": module_entry_groups,
        "role_workbenches": role_workbenches,
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


def _observability_operator_suggestions(
    overview: ObservabilityOverviewRead,
    slo_overview: ObservabilitySloOverviewRead,
    alert_events: list[Any],
) -> list[dict[str, str]]:
    suggestions: list[dict[str, str]] = []
    total_signals = max(overview.total_signals, 1)
    error_ratio = overview.error_signals / total_signals if overview.total_signals else 0.0

    if overview.total_signals == 0:
        suggestions.append(
            {
                "severity": "warn",
                "title": "Seed a synthetic watch sample",
                "detail": "No observability signals were found. Use the UI signal ingest action to create a baseline watch set.",
            }
        )
    elif error_ratio >= 0.2:
        suggestions.append(
            {
                "severity": "danger",
                "title": "Spend error budget immediately",
                "detail": (
                    f"Error ratio is {error_ratio:.0%} in the current watch window; "
                    "run SLO evaluation and review recent alert events."
                ),
            }
        )
    else:
        suggestions.append(
            {
                "severity": "success",
                "title": "Watch window is stable",
                "detail": (
                    f"{overview.total_signals} signals collected with {overview.error_signals} errors; "
                    "continue routine watch and keep SLO sampling current."
                ),
            }
        )

    if slo_overview.breached_count:
        suggestions.append(
            {
                "severity": "warn",
                "title": "Prioritize breached SLOs",
                "detail": (
                    f"{slo_overview.breached_count} SLO evaluations are currently breached; "
                    "use the replay section to inspect impacted policies."
                ),
            }
        )
    elif slo_overview.policy_count:
        suggestions.append(
            {
                "severity": "success",
                "title": "SLO posture is green",
                "detail": (
                    f"{slo_overview.healthy_count} of {slo_overview.policy_count} tracked policies are healthy."
                ),
            }
        )
    else:
        suggestions.append(
            {
                "severity": "warn",
                "title": "Create the first SLO policy",
                "detail": "No SLO policy exists yet. Create one for the most critical service before scaling further.",
            }
        )

    open_alerts = [
        item for item in alert_events if getattr(item, "status", None) != ObservabilityAlertStatus.CLOSED
    ]
    if open_alerts:
        latest_alert = open_alerts[0]
        suggestions.append(
            {
                "severity": "warn",
                "title": "Keep the oncall chain active",
                "detail": (
                    f"{len(open_alerts)} alert events remain open; latest is "
                    f"{getattr(latest_alert, 'title', 'unnamed alert')}."
                ),
            }
        )
    else:
        suggestions.append(
            {
                "severity": "success",
                "title": "No unclosed observability alerts",
                "detail": "Current watch history has no open alert event backlog.",
            }
        )

    return suggestions


def _reliability_operator_suggestions(
    backups: list[Any],
    restore_drills: list[ReliabilityRestoreDrillRead],
    security_runs: list[dict[str, Any]],
    capacity_policies: list[CapacityPolicyRead],
    capacity_forecasts: list[Any],
) -> list[dict[str, str]]:
    suggestions: list[dict[str, str]] = []

    if backups:
        latest_backup = backups[0]
        suggestions.append(
            {
                "severity": "success",
                "title": "Backup cadence is present",
                "detail": (
                    f"Latest backup run {latest_backup.id} is {latest_backup.status}; "
                    "keep restore drill evidence tied to recent runs."
                ),
            }
        )
    else:
        suggestions.append(
            {
                "severity": "warn",
                "title": "Run the first backup baseline",
                "detail": "No backup run is recorded. Start with a full drill-friendly backup before opening the ops shift.",
            }
        )

    if restore_drills:
        latest_drill = restore_drills[0]
        drill_severity = "success" if latest_drill.status.value == "PASSED" else "danger"
        suggestions.append(
            {
                "severity": drill_severity,
                "title": "Restore readiness has recent evidence",
                "detail": (
                    f"Latest restore drill finished {latest_drill.status} with actual RTO "
                    f"{latest_drill.actual_rto_seconds}s."
                ),
            }
        )
    else:
        suggestions.append(
            {
                "severity": "warn",
                "title": "Schedule a restore drill",
                "detail": "Backups exist without restore validation. Run a drill to confirm tenant recovery objectives.",
            }
        )

    if security_runs:
        latest_security = security_runs[0]["run"]
        security_severity = "danger" if latest_security.failed_checks else "success"
        suggestions.append(
            {
                "severity": security_severity,
                "title": "Track security remediation",
                "detail": (
                    f"Latest inspection scored {latest_security.score_percent:.1f}% with "
                    f"{latest_security.failed_checks} failed checks."
                ),
            }
        )
    else:
        suggestions.append(
            {
                "severity": "warn",
                "title": "Run a baseline security inspection",
                "detail": "No security inspection report is available for the current tenant.",
            }
        )

    if capacity_forecasts:
        latest_forecast = capacity_forecasts[0]
        forecast_severity = "warn" if latest_forecast.decision != CapacityDecision.HOLD else "success"
        suggestions.append(
            {
                "severity": forecast_severity,
                "title": "Capacity decision is ready",
                "detail": (
                    f"Latest forecast recommends {latest_forecast.decision} "
                    f"to {latest_forecast.recommended_replicas} replicas for {latest_forecast.meter_key}."
                ),
            }
        )
    elif capacity_policies:
        policy = capacity_policies[0]
        suggestions.append(
            {
                "severity": "warn",
                "title": "Policies exist but forecasts are stale",
                "detail": (
                    f"Capacity policy {policy.meter_key} is configured; generate a fresh forecast before "
                    "the next traffic window."
                ),
            }
        )
    else:
        suggestions.append(
            {
                "severity": "warn",
                "title": "Define a first capacity policy",
                "detail": "Capacity automation is not configured yet; create a policy for the primary runtime meter.",
            }
        )

    return suggestions


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
    role_workbenches = _visible_role_workbenches(claims)
    featured_workbench = role_workbenches[0] if role_workbenches else None
    return _render_console(
        request,
        template_name="ui_console.html",
        token=resolved_token,
        claims=claims,
        active_nav="console",
        title="角色化工作台",
        subtitle="按职责进入常用入口, 减少无关功能干扰。",
        session_from_query=from_query,
        stats=stats,
        role_workbenches=role_workbenches,
        featured_workbench=featured_workbench,
        attention_items=_console_attention_items(stats),
        next_steps=_workbench_next_steps(featured_workbench),
    )


@router.get("/ui/workbench/{role_key}")
def ui_role_workbench(request: Request, role_key: str, token: str | None = Query(default=None)) -> Response:
    try:
        resolved_token, claims, from_query = _resolve_ui_access(request, token=token)
    except HTTPException:
        return _login_redirect(request, clear_session=True)

    role_definition = _find_role_workbench(role_key)
    if role_definition is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="role workbench not found")
    if not _is_role_workbench_visible(claims, role_definition):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="insufficient permissions")

    stats = DashboardService().get_stats(claims["tenant_id"])
    role_workbench = next(
        (item for item in _visible_role_workbenches(claims) if item["key"] == role_key),
        None,
    )
    if role_workbench is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="role workbench unavailable")

    return _render_console(
        request,
        template_name="ui_role_workbench.html",
        token=resolved_token,
        claims=claims,
        active_nav="console",
        title=role_definition.label,
        subtitle=role_definition.summary,
        session_from_query=from_query,
        workbench=role_workbench,
        stats=stats,
        attention_items=_console_attention_items(stats),
        next_steps=_workbench_next_steps(role_workbench),
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
        title="巡检任务",
        subtitle="查看巡检任务、进入详情并快速发起新任务。",
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
        title=f"巡检任务 {task.id}",
        subtitle="查看任务详情、观察地图并执行导出或缺陷关联。",
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
        title="缺陷闭环",
        subtitle="围绕缺陷分派、状态更新和详情追踪完成闭环。",
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
        title="应急处置",
        subtitle="围绕当前事件完成坐标确认、事件建单和任务联动。",
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
        title="一张图指挥中心",
        subtitle="以地图为主工作面, 统一查看设备、任务、空域、告警、事件、成果与联动入口。",
        session_from_query=from_query,
        stats=stats,
    )


@router.get("/ui/observability")
def ui_observability(request: Request, token: str | None = Query(default=None)) -> Response:
    try:
        resolved_token, claims, from_query = _resolve_ui_access(
            request,
            token=token,
            required_permission=PERM_OBSERVABILITY_READ,
        )
    except HTTPException as exc:
        if exc.status_code == status.HTTP_401_UNAUTHORIZED:
            return _login_redirect(request, clear_session=True)
        raise

    service = ObservabilityService()
    can_observability_write = has_permission(claims, PERM_OBSERVABILITY_WRITE)

    overview = service.get_overview(claims["tenant_id"], window_minutes=180)
    slo_overview = service.get_slo_overview(claims["tenant_id"])
    signals = service.list_signals(claims["tenant_id"], limit=20)
    slo_policies = service.list_slo_policies(claims["tenant_id"])
    slo_evaluations = service.list_slo_evaluations(claims["tenant_id"], limit=12)
    alert_events = service.list_alert_events(claims["tenant_id"], limit=12)
    operator_suggestions = _observability_operator_suggestions(overview, slo_overview, alert_events)

    return _render_console(
        request,
        template_name="ui_observability.html",
        token=resolved_token,
        claims=claims,
        active_nav="observability",
        title="可观测值守 (管理员)",
        subtitle="管理员技术页: 统一查看信号、SLO 与告警回放, 不作为日常业务入口。",
        session_from_query=from_query,
        overview=overview,
        slo_overview=slo_overview,
        signals=signals,
        slo_policies=slo_policies,
        slo_evaluations=slo_evaluations,
        alert_events=alert_events,
        operator_suggestions=operator_suggestions,
        can_observability_write=can_observability_write,
        observability_signal_type_options=[item.value for item in ObservabilitySignalType],
        observability_signal_level_options=[item.value for item in ObservabilitySignalLevel],
        observability_slo_status_options=[item.value for item in ObservabilitySloStatus],
        observability_alert_status_options=[item.value for item in ObservabilityAlertStatus],
        observability_alert_severity_options=[item.value for item in ObservabilityAlertSeverity],
    )


@router.get("/ui/reliability")
def ui_reliability(request: Request, token: str | None = Query(default=None)) -> Response:
    try:
        resolved_token, claims, from_query = _resolve_ui_access(
            request,
            token=token,
            required_permission=PERM_OBSERVABILITY_READ,
        )
    except HTTPException as exc:
        if exc.status_code == status.HTTP_401_UNAUTHORIZED:
            return _login_redirect(request, clear_session=True)
        raise

    service = ObservabilityService()
    can_observability_write = has_permission(claims, PERM_OBSERVABILITY_WRITE)

    backups = service.list_backups(claims["tenant_id"], limit=12)
    restore_drills = [
        ReliabilityRestoreDrillRead.model_validate(item)
        for item in service.list_restore_drills(claims["tenant_id"], limit=12)
    ]
    security_runs: list[dict[str, Any]] = []
    for run, items in service.list_security_inspections(claims["tenant_id"], limit=10):
        failed_items = [item for item in items if item.status == SecurityInspectionCheckStatus.FAIL]
        security_runs.append(
            {
                "run": run,
                "items": items,
                "failed_items": failed_items,
            }
        )
    capacity_policies = [CapacityPolicyRead.model_validate(item) for item in service.list_capacity_policies(claims["tenant_id"])]
    capacity_forecasts = service.list_capacity_forecasts(claims["tenant_id"], limit=12)
    operator_suggestions = _reliability_operator_suggestions(
        backups,
        restore_drills,
        security_runs,
        capacity_policies,
        capacity_forecasts,
    )

    return _render_console(
        request,
        template_name="ui_reliability.html",
        token=resolved_token,
        claims=claims,
        active_nav="reliability",
        title="可靠性运行 (管理员)",
        subtitle="管理员技术页: 处理备份、演练与容量策略, 不作为日常业务入口。",
        session_from_query=from_query,
        backups=backups,
        restore_drills=restore_drills,
        security_runs=security_runs,
        capacity_policies=capacity_policies,
        capacity_forecasts=capacity_forecasts,
        operator_suggestions=operator_suggestions,
        can_observability_write=can_observability_write,
        reliability_backup_run_type_options=[item.value for item in ReliabilityBackupRunType],
        observability_capacity_decision_options=[item.value for item in CapacityDecision],
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
        title="任务中心",
        subtitle="围绕当前选中任务完成流转、派发、审批和评论。",
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
        title="资产台账",
        subtitle="先选中资产, 再完成状态更新、维护工单和资源池管理。",
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
        title="合规治理",
        subtitle="围绕审批、空域规则和决策留痕完成合规处理与审计准备。",
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
    can_mission_read = has_permission(claims, PERM_MISSION_READ)
    can_approval_read = has_permission(claims, PERM_APPROVAL_READ)
    task_rows: list[Any] = []
    approval_rows: list[Any] = []
    unified_todos: list[dict[str, Any]] = []
    message_center_items: list[dict[str, Any]] = []
    collaboration_cards: list[dict[str, Any]] = []
    channel_cards: list[dict[str, Any]] = []
    escalation_watch_items: list[dict[str, Any]] = []
    role_priorities: list[dict[str, Any]] = []

    if can_mission_read:
        task_rows = TaskCenterService().list_tasks(
            claims["tenant_id"],
            viewer_user_id=claims["sub"],
        )
    if can_approval_read:
        approval_rows = ComplianceService().list_approvals(claims["tenant_id"])

    def _task_state_label(value: str) -> str:
        mapping = {
            "DRAFT": "待完善",
            "APPROVAL_PENDING": "待审批",
            "READY": "待派发",
            "DISPATCHED": "待接单",
            "ACCEPTED": "待执行",
            "IN_PROGRESS": "执行中",
            "COMPLETED": "待归档",
            "CANCELED": "已取消",
            "ARCHIVED": "已归档",
        }
        return mapping.get(value, value)

    def _alert_status_label(value: str) -> str:
        mapping = {
            AlertStatus.OPEN.value: "待响应",
            AlertStatus.ACKED.value: "已确认",
            AlertStatus.CLOSED.value: "已关闭",
        }
        return mapping.get(value, value)

    def _alert_priority_label(value: str) -> str:
        mapping = {
            AlertPriority.P1.value: "高",
            AlertPriority.P2.value: "中",
            AlertPriority.P3.value: "低",
        }
        return mapping.get(value, value)

    def _priority_rank(level: str, fallback: int = 9) -> int:
        order = {
            "高": 1,
            "中": 2,
            "低": 3,
            "待审批": 2,
            "待响应": 1,
            "待派发": 2,
            "待接单": 2,
            "待执行": 2,
            "执行中": 3,
        }
        return order.get(level, fallback)

    open_alerts: list[Any] = [item for item in alerts if item.status == AlertStatus.OPEN]
    active_tasks: list[Any] = [
        item
        for item in task_rows
        if str(getattr(item.state, "value", item.state)) not in {"COMPLETED", "CANCELED", "ARCHIVED"}
    ]
    pending_approvals: list[Any] = [item for item in approval_rows if str(item.status).upper() != "APPROVED"]

    for item in open_alerts[:6]:
        priority_label = _alert_priority_label(item.priority_level.value)
        unified_todos.append(
            {
                "kind": "告警",
                "title": item.message or "待处理告警",
                "subtitle": f"{item.alert_type.value} · 设备 {item.drone_id}",
                "status_label": _alert_status_label(item.status.value),
                "priority_label": priority_label,
                "priority_rank": _priority_rank(priority_label),
                "time_label": item.last_seen_at.strftime("%Y-%m-%d %H:%M"),
                "action_label": "处理告警",
                "action_href": "",
                "select_alert_id": item.id,
            }
        )
        message_center_items.append(
            {
                "channel": "系统告警",
                "title": item.message or "待处理告警",
                "meta": f"{item.alert_type.value} · {_alert_status_label(item.status.value)}",
                "time_label": item.last_seen_at.strftime("%Y-%m-%d %H:%M"),
                "tone": "warn",
            }
        )

    for item in pending_approvals[:5]:
        status_value = str(item.status)
        unified_todos.append(
            {
                "kind": "审批",
                "title": f"{item.entity_type} 审批待处理",
                "subtitle": f"对象 {item.entity_id}",
                "status_label": "待审批" if status_value.upper() != "APPROVED" else "已通过",
                "priority_label": "中",
                "priority_rank": 2,
                "time_label": item.created_at.strftime("%Y-%m-%d %H:%M"),
                "action_label": "进入合规页",
                "action_href": f"/ui/compliance?token={resolved_token}",
                "select_alert_id": "",
            }
        )
        message_center_items.append(
            {
                "channel": "审批待办",
                "title": f"{item.entity_type} 待审批",
                "meta": f"{item.entity_id} · {status_value}",
                "time_label": item.created_at.strftime("%Y-%m-%d %H:%M"),
                "tone": "info",
            }
        )

    for item in active_tasks[:5]:
        state_value = str(getattr(item.state, "value", item.state))
        unified_todos.append(
            {
                "kind": "任务",
                "title": item.name,
                "subtitle": f"任务状态 {_task_state_label(state_value)} · 优先级 {item.priority}",
                "status_label": _task_state_label(state_value),
                "priority_label": "高" if int(item.priority) >= 8 else "中" if int(item.priority) >= 5 else "低",
                "priority_rank": 1 if int(item.priority) >= 8 else 2 if int(item.priority) >= 5 else 3,
                "time_label": item.updated_at.strftime("%Y-%m-%d %H:%M"),
                "action_label": "进入任务中心",
                "action_href": f"/ui/task-center?token={resolved_token}",
                "select_alert_id": "",
            }
        )
        message_center_items.append(
            {
                "channel": "任务待办",
                "title": item.name,
                "meta": f"{_task_state_label(state_value)} · 优先级 {item.priority}",
                "time_label": item.updated_at.strftime("%Y-%m-%d %H:%M"),
                "tone": "muted",
            }
        )

    unified_todos = sorted(unified_todos, key=lambda item: (item["priority_rank"], item["time_label"]))[:10]
    message_center_items = sorted(message_center_items, key=lambda item: item["time_label"], reverse=True)[:8]

    collaboration_cards = [
        {
            "label": "统一待办",
            "value": len(unified_todos),
            "note": "告警、审批、任务已合并到同一协同清单。",
            "tone": "info" if unified_todos else "muted",
        },
        {
            "label": "高优先级响应",
            "value": len([item for item in unified_todos if item["priority_rank"] == 1]),
            "note": "优先处理高风险或高优先级事项。",
            "tone": "warn" if len([item for item in unified_todos if item["priority_rank"] == 1]) else "success",
        },
        {
            "label": "待审批事项",
            "value": len(pending_approvals),
            "note": "由合规或审核角色集中推进。",
            "tone": "info" if pending_approvals else "muted",
        },
        {
            "label": "外部触达能力",
            "value": len(routing_rules) + len(oncall_shifts),
            "note": "通过路由规则和值守班次承接外部通知。",
            "tone": "info",
        },
    ]

    channel_cards = [
        {
            "label": "消息路由",
            "value": len(routing_rules),
            "note": "按优先级和类型决定通知去向。",
        },
        {
            "label": "值守班次",
            "value": len(oncall_shifts),
            "note": "承接值班人员轮转和目标切换。",
        },
        {
            "label": "升级策略",
            "value": len(escalation_policies),
            "note": "用于超时提醒、催办和逐级升级。",
        },
        {
            "label": "静默/聚合",
            "value": len(silence_rules) + len(aggregation_rules),
            "note": "控制通知噪音, 保持协同清晰。",
        },
    ]

    escalation_watch_items = [
        {
            "label": "待响应告警",
            "value": status_counter.get(AlertStatus.OPEN.value, 0),
            "note": "需要及时确认和分派。",
        },
        {
            "label": "已确认未闭环",
            "value": status_counter.get(AlertStatus.ACKED.value, 0),
            "note": "适合作为催办和跟踪对象。",
        },
        {
            "label": "值守班次覆盖",
            "value": len(oncall_shifts),
            "note": "确保关键时段有人接收提醒。",
        },
        {
            "label": "升级策略覆盖",
            "value": len(escalation_policies),
            "note": "超时后可自动进入升级链路。",
        },
    ]

    role_priorities = [
        {
            "role": "值守人员",
            "focus": "优先确认高优先级告警并提交回执。",
            "count": len(open_alerts),
            "href": f"/ui/alerts?token={resolved_token}",
        },
        {
            "role": "合规审核",
            "focus": "集中处理待审批事项, 避免任务停滞。",
            "count": len(pending_approvals),
            "href": f"/ui/compliance?token={resolved_token}",
        },
        {
            "role": "调度执行",
            "focus": "跟进待派发、待接单和执行中的任务。",
            "count": len(active_tasks),
            "href": f"/ui/task-center?token={resolved_token}",
        },
    ]

    return _render_console(
        request,
        template_name="ui_alerts.html",
        token=resolved_token,
        claims=claims,
        active_nav="alerts",
        title="通知协同中心",
        subtitle="先看统一待办和提醒, 再推进告警处理、催办升级与渠道策略。",
        session_from_query=from_query,
        alerts=alerts,
        unified_todos=unified_todos,
        message_center_items=message_center_items,
        collaboration_cards=collaboration_cards,
        channel_cards=channel_cards,
        escalation_watch_items=escalation_watch_items,
        role_priorities=role_priorities,
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
        can_mission_read=can_mission_read,
        can_approval_read=can_approval_read,
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
    closure_stages: list[dict[str, Any]] = []
    review_queue: list[dict[str, Any]] = []
    case_highlights: list[dict[str, Any]] = []
    topic_summary: list[dict[str, Any]] = []
    leadership_cards: list[dict[str, str]] = []
    leadership_focus: list[str] = []
    outcome_pending_count = 0
    outcome_verified_count = 0
    outcome_archived_count = 0

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

    def _enum_value(value: Any) -> str:
        raw = getattr(value, "value", value)
        return str(raw)

    def _source_label(value: str) -> str:
        mapping = {
            OutcomeSourceType.INSPECTION_OBSERVATION.value: "巡检发现",
            OutcomeSourceType.ALERT.value: "告警转入",
            OutcomeSourceType.MANUAL.value: "人工补录",
        }
        return mapping.get(value, value)

    def _type_label(value: str) -> str:
        mapping = {
            OutcomeType.DEFECT.value: "缺陷",
            OutcomeType.HIDDEN_RISK.value: "隐患",
            OutcomeType.INCIDENT.value: "事件",
            OutcomeType.OTHER.value: "其他",
        }
        return mapping.get(value, value)

    def _status_meta(value: str) -> tuple[str, str]:
        mapping = {
            OutcomeStatus.NEW.value: ("已发现", "warn"),
            OutcomeStatus.IN_REVIEW.value: ("整改中", "info"),
            OutcomeStatus.VERIFIED.value: ("待归档", "muted"),
            OutcomeStatus.ARCHIVED.value: ("已闭环", "success"),
        }
        return mapping.get(value, (value, "muted"))

    if can_inspection_read:
        sorted_outcomes = sorted(
            outcome_records,
            key=lambda item: getattr(item, "updated_at", getattr(item, "created_at", 0)),
            reverse=True,
        )
        outcome_status_counter = Counter(_enum_value(item.status) for item in sorted_outcomes)
        outcome_pending_count = (
            outcome_status_counter.get(OutcomeStatus.NEW.value, 0)
            + outcome_status_counter.get(OutcomeStatus.IN_REVIEW.value, 0)
        )
        outcome_verified_count = outcome_status_counter.get(OutcomeStatus.VERIFIED.value, 0)
        outcome_archived_count = outcome_status_counter.get(OutcomeStatus.ARCHIVED.value, 0)
        closure_stages = [
            {
                "label": "发现登记",
                "count": outcome_status_counter.get(OutcomeStatus.NEW.value, 0),
                "note": "等待安排整改或补充说明。",
                "tone": "warn",
            },
            {
                "label": "整改推进",
                "count": outcome_status_counter.get(OutcomeStatus.IN_REVIEW.value, 0),
                "note": "正在处理, 关注负责人和时效。",
                "tone": "info",
            },
            {
                "label": "复核确认",
                "count": outcome_status_counter.get(OutcomeStatus.VERIFIED.value, 0),
                "note": "处理完成, 等待最终归档。",
                "tone": "muted",
            },
            {
                "label": "闭环归档",
                "count": outcome_status_counter.get(OutcomeStatus.ARCHIVED.value, 0),
                "note": "已形成可复用案例与汇报材料。",
                "tone": "success",
            },
        ]

        for item in sorted_outcomes:
            payload = item.payload if isinstance(item.payload, dict) else {}
            summary = payload.get("note") or payload.get("summary") or payload.get("remark") or ""
            if not isinstance(summary, str):
                summary = str(summary)
            summary = summary.strip() or "待补充现场说明。"
            status_value = _enum_value(item.status)
            status_label, status_tone = _status_meta(status_value)
            review_queue.append(
                {
                    "id": item.id,
                    "title": f"{_type_label(_enum_value(item.outcome_type))}事项",
                    "summary": summary[:64],
                    "source_label": _source_label(_enum_value(item.source_type)),
                    "status_label": status_label,
                    "status_tone": status_tone,
                    "task_label": item.task_id or "未关联任务",
                    "updated_at_label": item.updated_at.strftime("%Y-%m-%d %H:%M"),
                    "task_id": item.task_id or "",
                }
            )
        review_queue = review_queue[:8]

        closed_candidates = [
            item for item in sorted_outcomes if _enum_value(item.status) in {OutcomeStatus.VERIFIED.value, OutcomeStatus.ARCHIVED.value}
        ]
        if not closed_candidates:
            closed_candidates = sorted_outcomes[:3]
        for item in closed_candidates[:3]:
            payload = item.payload if isinstance(item.payload, dict) else {}
            summary = payload.get("note") or payload.get("summary") or payload.get("remark") or ""
            if not isinstance(summary, str):
                summary = str(summary)
            status_label, status_tone = _status_meta(_enum_value(item.status))
            case_highlights.append(
                {
                    "id": item.id,
                    "title": f"{_type_label(_enum_value(item.outcome_type))}专题",
                    "summary": (summary.strip() or "已完成闭环, 可作为复盘案例。")[:88],
                    "source_label": _source_label(_enum_value(item.source_type)),
                    "status_label": status_label,
                    "status_tone": status_tone,
                    "task_label": item.task_id or "未关联任务",
                }
            )

        for outcome_type, count in Counter(_enum_value(item.outcome_type) for item in sorted_outcomes).most_common(4):
            topic_summary.append(
                {
                    "label": _type_label(outcome_type),
                    "count": count,
                    "note": f"近阶段累计沉淀 {count} 条相关成果, 可用于专题复盘。",
                }
            )

    if can_reporting_read:
        export_status_counter = Counter(_enum_value(item.status) for item in outcome_exports)
        latest_export = outcome_exports[0] if outcome_exports else None
        leadership_cards = [
            {
                "label": "当前闭环率",
                "value": f"{(closure_rate.get('closure_rate', 0.0) or 0.0) * 100:.1f}%",
                "note": f"已关闭 {closure_rate.get('closed', 0)} / {closure_rate.get('total', 0)} 个缺陷事项。",
                "tone": "success" if float(closure_rate.get("closure_rate", 0.0) or 0.0) >= 0.8 else "warn",
            },
            {
                "label": "待推进成果",
                "value": str(outcome_pending_count),
                "note": "优先安排整改与复核, 避免事项积压。",
                "tone": "warn" if outcome_pending_count else "success",
            },
            {
                "label": "案例沉淀",
                "value": str(outcome_archived_count),
                "note": "已归档的成果可直接用于汇报和培训复盘。",
                "tone": "info" if outcome_archived_count else "muted",
            },
            {
                "label": "汇报任务",
                "value": str(len(outcome_exports)),
                "note": f"已完成 {export_status_counter.get(ReportExportStatus.SUCCEEDED.value, 0)} 条, "
                f"进行中 {export_status_counter.get(ReportExportStatus.RUNNING.value, 0)} 条。",
                "tone": "info",
            },
        ]
        leadership_focus = [
            (
                f"当前任务覆盖 {overview.get('missions_total', 0)} 个任务批次, "
                f"累计形成 {len(outcome_records)} 条成果沉淀。"
            ),
            (
                f"待推进成果 {outcome_pending_count} 条, "
                f"待归档成果 {outcome_verified_count} 条, 建议优先清理复核队列。"
            ),
        ]
        if latest_export is not None:
            leadership_focus.append(
                f"最近汇报任务为 {latest_export.id}, 状态 {_enum_value(latest_export.status)}, 主题 {latest_export.topic or '综合复盘'}。"
            )
        if latest_snapshot is not None:
            metrics = latest_snapshot.metrics if isinstance(latest_snapshot.metrics, dict) else {}
            leadership_focus.append(
                f"最近经营快照窗口 {getattr(latest_snapshot.window_type, 'value', latest_snapshot.window_type)}, "
                f"覆盖 {len(metrics)} 项指标, 生成于 {latest_snapshot.generated_at.strftime('%Y-%m-%d %H:%M')}。"
            )

    return _render_console(
        request,
        template_name="ui_reports.html",
        token=resolved_token,
        claims=claims,
        active_nav="reports",
        title="业务闭环与汇报",
        subtitle="先看闭环进度和成果消费, 再按需进入数据调阅与汇报治理。",
        session_from_query=from_query,
        overview=overview,
        closure_rate=closure_rate,
        device_utilization=device_utilization,
        raw_records=raw_records,
        outcome_records=outcome_records,
        closure_stages=closure_stages,
        review_queue=review_queue,
        case_highlights=case_highlights,
        topic_summary=topic_summary,
        leadership_cards=leadership_cards,
        leadership_focus=leadership_focus,
        outcome_pending_count=outcome_pending_count,
        outcome_verified_count=outcome_verified_count,
        outcome_archived_count=outcome_archived_count,
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
        title="AI 治理 (管理员)",
        subtitle="管理员技术页: 处理模型、策略和证据链治理, 不作为日常业务入口。",
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
        title="商业运营 (管理员)",
        subtitle="管理员技术页: 处理计费、配额和租户运营, 不作为日常业务入口。",
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
        title="开放平台 (管理员)",
        subtitle="管理员技术页: 处理凭证、Webhook 和接入事件, 不作为日常业务入口。",
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
    current_tenant = tenants[0] if tenants else None
    active_users = len([item for item in users if item.is_active])
    custom_roles = len([item for item in roles if not getattr(item, "is_system", False)])
    active_org_units = len([item for item in org_units if item.is_active])
    onboarding_cards = [
        {
            "label": "当前租户",
            "value": current_tenant.name if current_tenant is not None else "未识别",
            "note": "先确认交付对象, 再补齐组织、角色和管理员准备。",
        },
        {
            "label": "启动准备",
            "value": active_org_units,
            "note": "已启用组织单元数量, 用于判断组织骨架是否完整。",
        },
        {
            "label": "账号准备",
            "value": active_users,
            "note": "建议至少保留交付管理员、运维联系人和培训账号。",
        },
        {
            "label": "角色模板复用",
            "value": len(role_templates),
            "note": "优先从模板创建角色, 降低重复配置成本。",
        },
    ]
    config_packs = [
        {
            "name": "标准交付包",
            "key": "standard-delivery",
            "summary": "创建组织骨架、基础管理员角色和演示账号。",
            "pack_items": "组织骨架 / 管理角色 / 演示账号",
        },
        {
            "name": "培训演示包",
            "key": "training-pack",
            "summary": "强调培训账号、演示模式和复盘素材准备。",
            "pack_items": "培训账号 / 演示模式 / 汇报样板",
        },
        {
            "name": "生产上线包",
            "key": "production-pack",
            "summary": "强调生产模式、交接清单和留痕导出。",
            "pack_items": "生产模式 / 交接清单 / 审计导出",
        },
    ]
    handoff_panels = [
        {
            "title": "客户交接",
            "checklist": [
                "确认租户名称、管理员账号和组织骨架。",
                "确认角色来源于标准模板, 避免现场手工配置。",
                "完成培训模式演示后, 再切到生产模式。",
            ],
        },
        {
            "title": "运维交接",
            "checklist": [
                "保留租户导出与角色模板清单, 便于后续巡检。",
                "确认平台治理矩阵与权限范围符合交付约束。",
                "记录演示、培训、生产三种模式的启用口径。",
            ],
        },
    ]
    release_checklist_cards = [
        {
            "key": "tenant-ready",
            "label": "租户确认",
            "status_label": "已就绪" if current_tenant is not None else "待处理",
            "status_tone": "success" if current_tenant is not None else "warn",
            "summary": "确认交付对象, 租户名称和上线范围, 避免跨租户误操作。",
        },
        {
            "key": "org-ready",
            "label": "组织骨架",
            "status_label": "已就绪" if active_org_units else "待处理",
            "status_tone": "success" if active_org_units else "warn",
            "summary": "至少保留一个启用组织单元, 确保账号和角色有明确挂载位置。",
        },
        {
            "key": "account-ready",
            "label": "账号准备",
            "status_label": "已就绪" if active_users else "待处理",
            "status_tone": "success" if active_users else "warn",
            "summary": "至少准备交付管理员, 培训账号或运维联系人, 便于交接和试运行。",
        },
        {
            "key": "role-ready",
            "label": "角色基线",
            "status_label": "已就绪" if role_templates else "待处理",
            "status_tone": "success" if role_templates else "warn",
            "summary": "优先复用标准模板, 避免现场手工拼装角色造成权限漂移。",
        },
    ]
    help_center_cards = [
        {
            "key": "daily-duty",
            "title": "值守上手指南",
            "audience": "值班指挥 / 调度",
            "summary": "用三步完成值守上手: 看态势, 看待办, 看风险, 再决定进入哪个工作台。",
            "steps": [
                "先进入工作台, 确认当前角色入口和当班重点。",
                "在通知协同中心处理高优消息与待办。",
                "需要追溯时, 从一张图或业务闭环页进入详情。",
            ],
        },
        {
            "key": "training-drill",
            "title": "培训演练脚本",
            "audience": "培训讲师 / 客户管理员",
            "summary": "把培训模式固定成标准话术, 减少口头传递和临场解释成本。",
            "steps": [
                "切换到培训模式, 使用培训账号进行演练。",
                "按巡检向导和应急向导完整走一遍。",
                "最后用业务闭环与汇报页完成复盘讲解。",
            ],
        },
        {
            "key": "go-live",
            "title": "正式上线说明",
            "audience": "交付 / 运维",
            "summary": "正式上线前确认账号、组织、角色、模式和交接清单全部就绪。",
            "steps": [
                "完成上线检查清单, 不带着待处理项直接切生产。",
                "通知关键角色确认使用口径和联系人。",
                "保留租户导出与发布说明, 便于后续巡检。",
            ],
        },
    ]
    release_notes = [
        {
            "key": "v39-go-live",
            "version": "v39",
            "title": "上线保障与版本运营台",
            "summary": "把上线检查、帮助中心、发布说明和灰度启用收敛到同一页, 减少上线前后页面跳转。",
            "impact": "交付与运维口径统一",
            "next_action": "建议先完成上线检查, 再切换生产模式。",
        },
        {
            "key": "v38-onboarding",
            "version": "v38",
            "title": "开通运营台基线",
            "summary": "保留租户开通向导、标准配置包和交接面板, 继续作为上线前准备入口。",
            "impact": "开通与交接路径不回退",
            "next_action": "未完成组织、角色和账号准备时, 优先补齐开通动作。",
        },
        {
            "key": "v37-collaboration",
            "version": "v37",
            "title": "通知协同中心联动",
            "summary": "上线后仍建议通过通知协同中心追踪关键消息、待办和升级路径。",
            "impact": "减少版本切换后的角色混乱",
            "next_action": "将关键通知口径同步给值守、合规和管理员角色。",
        },
    ]
    feature_flags = [
        {
            "key": "guided-workflows",
            "label": "向导式任务主路径",
            "recommended_state": "建议开启",
            "state_tone": "success",
            "summary": "保持巡检、应急和交付向导作为主路径, 避免回退到手工参数操作。",
        },
        {
            "key": "training-copy",
            "label": "培训提示与内置帮助",
            "recommended_state": "建议开启",
            "state_tone": "info",
            "summary": "在培训和试运行阶段展示更强的操作提示, 降低新用户上手成本。",
        },
        {
            "key": "gray-release",
            "label": "灰度启用提示",
            "recommended_state": "按需开启",
            "state_tone": "warn",
            "summary": "正式上线前先让管理员和关键岗位试用, 再逐步扩大可见范围。",
        },
    ]
    risk_panels = [
        {
            "title": "上线前巡检",
            "checklist": [
                "确认角色工作台与主业务页都保持中文化和向导化体验。",
                "确认只读角色不会看到管理员高级配置或写入按钮。",
                "确认培训模式与生产模式的话术、账号和数据边界已区分。",
            ],
        },
        {
            "title": "版本发布后观察",
            "checklist": [
                "重点观察消息中心、工作台首页和平台页是否存在口径冲突。",
                "发现培训话术和生产话术不一致时, 优先更新内置帮助提示。",
                "对临时关闭的功能保留明确说明, 避免用户误认为系统故障。",
            ],
        },
    ]

    return _render_console(
        request,
        template_name="ui_platform.html",
        token=resolved_token,
        claims=claims,
        active_nav="platform",
        title="上线保障与版本运营台",
        subtitle="在开通基线之上继续完成上线检查、培训引导、发布说明和灰度启用。",
        session_from_query=from_query,
        tenants=tenants,
        current_tenant=current_tenant,
        users=users,
        roles=roles,
        org_units=org_units,
        role_templates=role_templates,
        active_users=active_users,
        custom_roles=custom_roles,
        active_org_units=active_org_units,
        onboarding_cards=onboarding_cards,
        config_packs=config_packs,
        handoff_panels=handoff_panels,
        release_checklist_cards=release_checklist_cards,
        help_center_cards=help_center_cards,
        release_notes=release_notes,
        feature_flags=feature_flags,
        risk_panels=risk_panels,
        visibility_matrix=_resolved_ui_visibility_matrix(claims),
        can_identity_write=has_permission(claims, PERM_IDENTITY_WRITE),
        org_unit_type_options=[item.value for item in OrgUnitType],
    )
