from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.infra.auth import decode_access_token
from app.services.dashboard_service import DashboardService
from app.services.defect_service import DefectService
from app.services.incident_service import IncidentService
from app.services.inspection_service import InspectionService

router = APIRouter()
templates = Jinja2Templates(directory=str(Path("app") / "web" / "templates"))


def _resolve_claims(token: str | None) -> dict[str, Any]:
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="token is required")
    try:
        claims = decode_access_token(token)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token") from exc
    if not isinstance(claims.get("tenant_id"), str):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token tenant")
    return claims


@router.get("/ui")
def ui_root(token: str | None = Query(default=None)) -> RedirectResponse:
    query = f"?{urlencode({'token': token})}" if token else ""
    return RedirectResponse(url=f"/ui/inspection{query}", status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@router.get("/ui/inspection")
def ui_inspection(request: Request, token: str | None = Query(default=None)) -> Any:
    claims = _resolve_claims(token)
    service = InspectionService()
    tasks = service.list_tasks(claims["tenant_id"])
    return templates.TemplateResponse(
        request=request,
        name="inspection_list.html",
        context={"token": token, "tenant_id": claims["tenant_id"], "tasks": tasks},
    )


@router.get("/ui/inspection/tasks/{task_id}")
def ui_inspection_task(request: Request, task_id: str, token: str | None = Query(default=None)) -> Any:
    claims = _resolve_claims(token)
    service = InspectionService()
    task = service.get_task(claims["tenant_id"], task_id)
    observations = service.list_observations(claims["tenant_id"], task_id)
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
    return templates.TemplateResponse(
        request=request,
        name="inspection_task_detail.html",
        context={
            "token": token,
            "tenant_id": claims["tenant_id"],
            "task": task,
            "observations": observations,
            "observations_json": observations_json,
        },
    )


@router.get("/ui/defects")
def ui_defects(request: Request, token: str | None = Query(default=None)) -> Any:
    claims = _resolve_claims(token)
    service = DefectService()
    defects = service.list_defects(claims["tenant_id"])
    return templates.TemplateResponse(
        request=request,
        name="defects.html",
        context={"token": token, "tenant_id": claims["tenant_id"], "defects": defects},
    )


@router.get("/ui/emergency")
def ui_emergency(request: Request, token: str | None = Query(default=None)) -> Any:
    claims = _resolve_claims(token)
    incidents = IncidentService().list_incidents(claims["tenant_id"])
    return templates.TemplateResponse(
        request=request,
        name="emergency.html",
        context={"token": token, "tenant_id": claims["tenant_id"], "incidents": incidents},
    )


@router.get("/ui/command-center")
def ui_command_center(request: Request, token: str | None = Query(default=None)) -> Any:
    claims = _resolve_claims(token)
    stats = DashboardService().get_stats(claims["tenant_id"])
    return templates.TemplateResponse(
        request=request,
        name="command_center.html",
        context={"token": token, "tenant_id": claims["tenant_id"], "stats": stats},
    )
