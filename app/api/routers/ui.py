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

    return _render_console(
        request,
        template_name="ui_alerts.html",
        token=resolved_token,
        claims=claims,
        active_nav="alerts",
        title="告警中心",
        subtitle="先处理当前告警, 再按需配置值守班次和升级策略。",
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
        title="报表中心",
        subtitle="以成果消费为主, 按需进入数据与导出操作。",
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

    return _render_console(
        request,
        template_name="ui_platform.html",
        token=resolved_token,
        claims=claims,
        active_nav="platform",
        title="平台治理",
        subtitle="面向管理员查看租户、角色、组织和可见性治理规则。",
        session_from_query=from_query,
        tenants=tenants,
        users=users,
        roles=roles,
        org_units=org_units,
        role_templates=role_templates,
        visibility_matrix=_resolved_ui_visibility_matrix(claims),
        can_identity_write=has_permission(claims, PERM_IDENTITY_WRITE),
    )
