from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.api.deps import get_current_claims, require_perm
from app.domain.models import (
    TaskCenterAttachmentAddRequest,
    TaskCenterCandidateScoreRead,
    TaskCenterCommentCreateRequest,
    TaskCenterCommentRead,
    TaskCenterDispatchMode,
    TaskCenterRiskChecklistUpdateRequest,
    TaskCenterState,
    TaskCenterTaskApproveRequest,
    TaskCenterTaskAutoDispatchRead,
    TaskCenterTaskAutoDispatchRequest,
    TaskCenterTaskBatchCreateRead,
    TaskCenterTaskBatchCreateRequest,
    TaskCenterTaskCreate,
    TaskCenterTaskDispatchRequest,
    TaskCenterTaskHistoryRead,
    TaskCenterTaskRead,
    TaskCenterTaskSubmitApprovalRequest,
    TaskCenterTaskTransitionRequest,
    TaskTemplateCloneRequest,
    TaskTemplateCreate,
    TaskTemplateRead,
    TaskTypeCatalogCreate,
    TaskTypeCatalogRead,
)
from app.domain.permissions import PERM_MISSION_APPROVE, PERM_MISSION_READ, PERM_MISSION_WRITE
from app.infra.audit import set_audit_context
from app.services.task_center_service import ConflictError, NotFoundError, TaskCenterService

router = APIRouter()


def get_task_center_service() -> TaskCenterService:
    return TaskCenterService()


Claims = Annotated[dict[str, Any], Depends(get_current_claims)]
Service = Annotated[TaskCenterService, Depends(get_task_center_service)]


def _template_read(row: Any) -> TaskTemplateRead:
    payload = row.model_dump()
    default_payload = payload.get("default_payload", {})
    if not isinstance(default_payload, dict):
        default_payload = {}
    payload["template_version"] = str(default_payload.get("template_version", "v2"))
    payload["route_template"] = default_payload.get("route_template", {})
    payload["payload_template"] = default_payload.get("payload_template", {})
    return TaskTemplateRead.model_validate(payload)


def _handle_error(exc: Exception) -> None:
    if isinstance(exc, NotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if isinstance(exc, ConflictError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    raise exc


@router.post(
    "/types",
    response_model=TaskTypeCatalogRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_perm(PERM_MISSION_WRITE))],
)
def create_task_type(
    payload: TaskTypeCatalogCreate,
    request: Request,
    claims: Claims,
    service: Service,
) -> TaskTypeCatalogRead:
    set_audit_context(
        request,
        action="task_center.task_type.create",
        detail={"what": {"code": payload.code}},
    )
    try:
        row = service.create_task_type(claims["tenant_id"], claims["sub"], payload)
        return TaskTypeCatalogRead.model_validate(row)
    except (NotFoundError, ConflictError) as exc:
        _handle_error(exc)
        raise


@router.get(
    "/types",
    response_model=list[TaskTypeCatalogRead],
    dependencies=[Depends(require_perm(PERM_MISSION_READ))],
)
def list_task_types(
    claims: Claims,
    service: Service,
    is_active: bool | None = None,
) -> list[TaskTypeCatalogRead]:
    rows = service.list_task_types(claims["tenant_id"], is_active=is_active)
    return [TaskTypeCatalogRead.model_validate(item) for item in rows]


@router.post(
    "/templates",
    response_model=TaskTemplateRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_perm(PERM_MISSION_WRITE))],
)
def create_template(
    payload: TaskTemplateCreate,
    request: Request,
    claims: Claims,
    service: Service,
) -> TaskTemplateRead:
    set_audit_context(
        request,
        action="task_center.template.create",
        detail={"what": {"task_type_id": payload.task_type_id, "template_key": payload.template_key}},
    )
    try:
        row = service.create_template(claims["tenant_id"], claims["sub"], payload)
        return _template_read(row)
    except (NotFoundError, ConflictError) as exc:
        _handle_error(exc)
        raise


@router.get(
    "/templates",
    response_model=list[TaskTemplateRead],
    dependencies=[Depends(require_perm(PERM_MISSION_READ))],
)
def list_templates(
    claims: Claims,
    service: Service,
    task_type_id: str | None = None,
    is_active: bool | None = None,
) -> list[TaskTemplateRead]:
    rows = service.list_templates(
        claims["tenant_id"],
        task_type_id=task_type_id,
        is_active=is_active,
    )
    return [_template_read(item) for item in rows]


@router.post(
    "/templates/{template_id}:clone",
    response_model=TaskTemplateRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_perm(PERM_MISSION_WRITE))],
)
def clone_template(
    template_id: str,
    payload: TaskTemplateCloneRequest,
    request: Request,
    claims: Claims,
    service: Service,
) -> TaskTemplateRead:
    set_audit_context(
        request,
        action="task_center.template.clone",
        detail={"what": {"template_id": template_id, "template_key": payload.template_key}},
    )
    try:
        row = service.clone_template(claims["tenant_id"], template_id, claims["sub"], payload)
        return _template_read(row)
    except (NotFoundError, ConflictError) as exc:
        _handle_error(exc)
        raise


@router.post(
    "/tasks",
    response_model=TaskCenterTaskRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_perm(PERM_MISSION_WRITE))],
)
def create_task(
    payload: TaskCenterTaskCreate,
    request: Request,
    claims: Claims,
    service: Service,
) -> TaskCenterTaskRead:
    set_audit_context(
        request,
        action="task_center.task.create",
        detail={
            "what": {
                "task_type_id": payload.task_type_id,
                "template_id": payload.template_id,
                "mission_id": payload.mission_id,
            }
        },
    )
    try:
        row = service.create_task(claims["tenant_id"], claims["sub"], payload)
        return TaskCenterTaskRead.model_validate(row)
    except (NotFoundError, ConflictError) as exc:
        _handle_error(exc)
        raise


@router.post(
    "/tasks:batch-create",
    response_model=TaskCenterTaskBatchCreateRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_perm(PERM_MISSION_WRITE))],
)
def create_tasks_batch(
    payload: TaskCenterTaskBatchCreateRequest,
    request: Request,
    claims: Claims,
    service: Service,
) -> TaskCenterTaskBatchCreateRead:
    set_audit_context(
        request,
        action="task_center.task.batch_create",
        detail={"what": {"count": len(payload.tasks)}},
    )
    try:
        rows = service.create_tasks_batch(claims["tenant_id"], claims["sub"], payload)
        return TaskCenterTaskBatchCreateRead(
            total=len(rows),
            tasks=[TaskCenterTaskRead.model_validate(item) for item in rows],
        )
    except (NotFoundError, ConflictError) as exc:
        _handle_error(exc)
        raise


@router.get(
    "/tasks",
    response_model=list[TaskCenterTaskRead],
    dependencies=[Depends(require_perm(PERM_MISSION_READ))],
)
def list_tasks(
    claims: Claims,
    service: Service,
    state: Annotated[TaskCenterState | None, Query(alias="state")] = None,
) -> list[TaskCenterTaskRead]:
    rows = service.list_tasks(claims["tenant_id"], state=state, viewer_user_id=claims["sub"])
    return [TaskCenterTaskRead.model_validate(item) for item in rows]


@router.get(
    "/tasks/{task_id}",
    response_model=TaskCenterTaskRead,
    dependencies=[Depends(require_perm(PERM_MISSION_READ))],
)
def get_task(task_id: str, claims: Claims, service: Service) -> TaskCenterTaskRead:
    try:
        row = service.get_task(claims["tenant_id"], task_id, viewer_user_id=claims["sub"])
        return TaskCenterTaskRead.model_validate(row)
    except (NotFoundError, ConflictError) as exc:
        _handle_error(exc)
        raise


@router.post(
    "/tasks/{task_id}/submit-approval",
    response_model=TaskCenterTaskRead,
    dependencies=[Depends(require_perm(PERM_MISSION_WRITE))],
)
def submit_for_approval(
    task_id: str,
    payload: TaskCenterTaskSubmitApprovalRequest,
    request: Request,
    claims: Claims,
    service: Service,
) -> TaskCenterTaskRead:
    set_audit_context(
        request,
        action="task_center.task.submit_approval",
        detail={"what": {"task_id": task_id}},
    )
    try:
        row = service.submit_for_approval(
            claims["tenant_id"],
            task_id,
            claims["sub"],
            payload,
            viewer_user_id=claims["sub"],
        )
        return TaskCenterTaskRead.model_validate(row)
    except (NotFoundError, ConflictError) as exc:
        _handle_error(exc)
        raise


@router.post(
    "/tasks/{task_id}/approve",
    response_model=TaskCenterTaskRead,
    dependencies=[Depends(require_perm(PERM_MISSION_APPROVE))],
)
def approve_task(
    task_id: str,
    payload: TaskCenterTaskApproveRequest,
    request: Request,
    claims: Claims,
    service: Service,
) -> TaskCenterTaskRead:
    set_audit_context(
        request,
        action="task_center.task.approve",
        detail={"what": {"task_id": task_id, "decision": payload.decision}},
    )
    try:
        row = service.approve_task(
            claims["tenant_id"],
            task_id,
            claims["sub"],
            payload,
            viewer_user_id=claims["sub"],
        )
        return TaskCenterTaskRead.model_validate(row)
    except (NotFoundError, ConflictError) as exc:
        _handle_error(exc)
        raise


@router.post(
    "/tasks/{task_id}/dispatch",
    response_model=TaskCenterTaskRead,
    dependencies=[Depends(require_perm(PERM_MISSION_WRITE))],
)
def dispatch_task(
    task_id: str,
    payload: TaskCenterTaskDispatchRequest,
    request: Request,
    claims: Claims,
    service: Service,
) -> TaskCenterTaskRead:
    set_audit_context(
        request,
        action="task_center.task.dispatch",
        detail={"what": {"task_id": task_id, "assigned_to": payload.assigned_to}},
    )
    try:
        row = service.dispatch_task(
            claims["tenant_id"],
            task_id,
            claims["sub"],
            payload,
            viewer_user_id=claims["sub"],
        )
        return TaskCenterTaskRead.model_validate(row)
    except (NotFoundError, ConflictError) as exc:
        _handle_error(exc)
        raise


@router.post(
    "/tasks/{task_id}/auto-dispatch",
    response_model=TaskCenterTaskAutoDispatchRead,
    dependencies=[Depends(require_perm(PERM_MISSION_WRITE))],
)
def auto_dispatch_task(
    task_id: str,
    payload: TaskCenterTaskAutoDispatchRequest,
    request: Request,
    claims: Claims,
    service: Service,
) -> TaskCenterTaskAutoDispatchRead:
    set_audit_context(
        request,
        action="task_center.task.auto_dispatch",
        detail={"what": {"task_id": task_id, "candidate_count": len(payload.candidate_user_ids)}},
    )
    try:
        row, scores, resource_snapshot = service.auto_dispatch_task(
            claims["tenant_id"],
            task_id,
            claims["sub"],
            payload,
            viewer_user_id=claims["sub"],
        )
        return TaskCenterTaskAutoDispatchRead(
            task=TaskCenterTaskRead.model_validate(row),
            selected_user_id=row.assigned_to or "",
            dispatch_mode=row.dispatch_mode or TaskCenterDispatchMode.AUTO,
            scores=[TaskCenterCandidateScoreRead.model_validate(item) for item in scores],
            resource_snapshot=resource_snapshot,
        )
    except (NotFoundError, ConflictError) as exc:
        _handle_error(exc)
        raise


@router.post(
    "/tasks/{task_id}/transition",
    response_model=TaskCenterTaskRead,
    dependencies=[Depends(require_perm(PERM_MISSION_WRITE))],
)
def transition_task(
    task_id: str,
    payload: TaskCenterTaskTransitionRequest,
    request: Request,
    claims: Claims,
    service: Service,
) -> TaskCenterTaskRead:
    set_audit_context(
        request,
        action="task_center.task.transition",
        detail={"what": {"task_id": task_id, "target_state": payload.target_state}},
    )
    try:
        row = service.transition_task(
            claims["tenant_id"],
            task_id,
            claims["sub"],
            payload,
            viewer_user_id=claims["sub"],
        )
        return TaskCenterTaskRead.model_validate(row)
    except (NotFoundError, ConflictError) as exc:
        _handle_error(exc)
        raise


@router.patch(
    "/tasks/{task_id}/risk-checklist",
    response_model=TaskCenterTaskRead,
    dependencies=[Depends(require_perm(PERM_MISSION_WRITE))],
)
def update_risk_checklist(
    task_id: str,
    payload: TaskCenterRiskChecklistUpdateRequest,
    request: Request,
    claims: Claims,
    service: Service,
) -> TaskCenterTaskRead:
    set_audit_context(
        request,
        action="task_center.task.risk_checklist.update",
        detail={"what": {"task_id": task_id}},
    )
    try:
        row = service.update_risk_checklist(
            claims["tenant_id"],
            task_id,
            claims["sub"],
            payload,
            viewer_user_id=claims["sub"],
        )
        return TaskCenterTaskRead.model_validate(row)
    except (NotFoundError, ConflictError) as exc:
        _handle_error(exc)
        raise


@router.post(
    "/tasks/{task_id}/attachments",
    response_model=TaskCenterTaskRead,
    dependencies=[Depends(require_perm(PERM_MISSION_WRITE))],
)
def add_attachment(
    task_id: str,
    payload: TaskCenterAttachmentAddRequest,
    request: Request,
    claims: Claims,
    service: Service,
) -> TaskCenterTaskRead:
    set_audit_context(
        request,
        action="task_center.task.attachment.add",
        detail={"what": {"task_id": task_id, "name": payload.name}},
    )
    try:
        row = service.add_attachment(
            claims["tenant_id"],
            task_id,
            claims["sub"],
            payload,
            viewer_user_id=claims["sub"],
        )
        return TaskCenterTaskRead.model_validate(row)
    except (NotFoundError, ConflictError) as exc:
        _handle_error(exc)
        raise


@router.post(
    "/tasks/{task_id}/comments",
    response_model=TaskCenterCommentRead,
    dependencies=[Depends(require_perm(PERM_MISSION_WRITE))],
)
def add_comment(
    task_id: str,
    payload: TaskCenterCommentCreateRequest,
    request: Request,
    claims: Claims,
    service: Service,
) -> TaskCenterCommentRead:
    set_audit_context(
        request,
        action="task_center.task.comment.add",
        detail={"what": {"task_id": task_id}},
    )
    try:
        comment = service.add_comment(
            claims["tenant_id"],
            task_id,
            claims["sub"],
            payload,
            viewer_user_id=claims["sub"],
        )
        return TaskCenterCommentRead.model_validate(comment)
    except (NotFoundError, ConflictError) as exc:
        _handle_error(exc)
        raise


@router.get(
    "/tasks/{task_id}/comments",
    response_model=list[TaskCenterCommentRead],
    dependencies=[Depends(require_perm(PERM_MISSION_READ))],
)
def list_comments(
    task_id: str,
    request: Request,
    claims: Claims,
    service: Service,
) -> list[TaskCenterCommentRead]:
    set_audit_context(
        request,
        action="task_center.task.comment.list",
        detail={"what": {"task_id": task_id}},
    )
    try:
        rows = service.list_comments(claims["tenant_id"], task_id, viewer_user_id=claims["sub"])
        return [TaskCenterCommentRead.model_validate(item) for item in rows]
    except (NotFoundError, ConflictError) as exc:
        _handle_error(exc)
        raise


@router.get(
    "/tasks/{task_id}/history",
    response_model=list[TaskCenterTaskHistoryRead],
    dependencies=[Depends(require_perm(PERM_MISSION_READ))],
)
def list_task_history(
    task_id: str,
    request: Request,
    claims: Claims,
    service: Service,
) -> list[TaskCenterTaskHistoryRead]:
    set_audit_context(
        request,
        action="task_center.task.history.list",
        detail={"what": {"task_id": task_id}},
    )
    try:
        rows = service.list_history(claims["tenant_id"], task_id, viewer_user_id=claims["sub"])
        return [TaskCenterTaskHistoryRead.model_validate(item) for item in rows]
    except (NotFoundError, ConflictError) as exc:
        _handle_error(exc)
        raise
