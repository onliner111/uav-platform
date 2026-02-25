from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.domain.models import (
    ApprovalDecision,
    Asset,
    AssetAvailabilityStatus,
    Mission,
    OrgUnit,
    TaskCenterAttachmentAddRequest,
    TaskCenterCommentCreateRequest,
    TaskCenterDispatchMode,
    TaskCenterRiskChecklistUpdateRequest,
    TaskCenterTask,
    TaskCenterTaskApproveRequest,
    TaskCenterTaskAutoDispatchRequest,
    TaskCenterTaskCreate,
    TaskCenterTaskDispatchRequest,
    TaskCenterTaskHistory,
    TaskCenterTaskSubmitApprovalRequest,
    TaskCenterTaskTransitionRequest,
    TaskTemplate,
    TaskTemplateCreate,
    TaskTypeCatalog,
    TaskTypeCatalogCreate,
    User,
    UserOrgMembership,
)
from app.domain.state_machine import TaskCenterState, can_task_center_transition
from app.infra.db import get_engine
from app.infra.events import event_bus
from app.services.data_perimeter_service import DataPerimeterService


class TaskCenterError(Exception):
    pass


class NotFoundError(TaskCenterError):
    pass


class ConflictError(TaskCenterError):
    pass


class TaskCenterService:
    def __init__(self) -> None:
        self._data_perimeter = DataPerimeterService()

    def _session(self) -> Session:
        return Session(get_engine(), expire_on_commit=False)

    def _get_scoped_task_type(self, session: Session, tenant_id: str, task_type_id: str) -> TaskTypeCatalog:
        row = session.exec(
            select(TaskTypeCatalog)
            .where(TaskTypeCatalog.tenant_id == tenant_id)
            .where(TaskTypeCatalog.id == task_type_id)
        ).first()
        if row is None:
            raise NotFoundError("task type not found")
        return row

    def _get_scoped_template(self, session: Session, tenant_id: str, template_id: str) -> TaskTemplate:
        row = session.exec(
            select(TaskTemplate)
            .where(TaskTemplate.tenant_id == tenant_id)
            .where(TaskTemplate.id == template_id)
        ).first()
        if row is None:
            raise NotFoundError("task template not found")
        return row

    def _get_scoped_task(self, session: Session, tenant_id: str, task_id: str) -> TaskCenterTask:
        row = session.exec(
            select(TaskCenterTask)
            .where(TaskCenterTask.tenant_id == tenant_id)
            .where(TaskCenterTask.id == task_id)
        ).first()
        if row is None:
            raise NotFoundError("task not found")
        return row

    def _ensure_visible(
        self,
        session: Session,
        tenant_id: str,
        viewer_user_id: str | None,
        task: TaskCenterTask,
    ) -> None:
        if viewer_user_id is None:
            return
        scope = self._data_perimeter.resolve_scope(session, tenant_id, viewer_user_id)
        if not self._data_perimeter.task_center_visible(task, scope):
            raise NotFoundError("task not found")

    def _ensure_scoped_org_unit(self, session: Session, tenant_id: str, org_unit_id: str) -> None:
        row = session.exec(
            select(OrgUnit)
            .where(OrgUnit.tenant_id == tenant_id)
            .where(OrgUnit.id == org_unit_id)
        ).first()
        if row is None:
            raise NotFoundError("org unit not found")

    def _ensure_scoped_user(self, session: Session, tenant_id: str, user_id: str) -> None:
        row = session.exec(
            select(User)
            .where(User.tenant_id == tenant_id)
            .where(User.id == user_id)
        ).first()
        if row is None:
            raise NotFoundError("user not found")

    def _list_candidate_users(
        self,
        session: Session,
        tenant_id: str,
        candidate_user_ids: list[str],
    ) -> list[User]:
        if candidate_user_ids:
            rows: list[User] = []
            for user_id in candidate_user_ids:
                row = session.exec(
                    select(User)
                    .where(User.tenant_id == tenant_id)
                    .where(User.id == user_id)
                ).first()
                if row is not None and row.is_active:
                    rows.append(row)
            return rows
        all_rows = list(
            session.exec(
                select(User)
                .where(User.tenant_id == tenant_id)
            ).all()
        )
        return [item for item in all_rows if item.is_active]

    def _candidate_workload(self, session: Session, tenant_id: str, user_id: str) -> int:
        rows = list(
            session.exec(
                select(TaskCenterTask)
                .where(TaskCenterTask.tenant_id == tenant_id)
                .where(TaskCenterTask.assigned_to == user_id)
            ).all()
        )
        active_states = {
            TaskCenterState.DISPATCHED,
            TaskCenterState.IN_PROGRESS,
            TaskCenterState.APPROVAL_PENDING,
            TaskCenterState.APPROVED,
        }
        return sum(1 for item in rows if item.state in active_states)

    def _candidate_in_org_unit(
        self,
        session: Session,
        tenant_id: str,
        user_id: str,
        org_unit_id: str | None,
    ) -> bool:
        if org_unit_id is None:
            return False
        row = session.exec(
            select(UserOrgMembership)
            .where(UserOrgMembership.tenant_id == tenant_id)
            .where(UserOrgMembership.user_id == user_id)
            .where(UserOrgMembership.org_unit_id == org_unit_id)
        ).first()
        return row is not None

    def _resource_snapshot(self, session: Session, tenant_id: str, area_code: str | None) -> dict[str, Any]:
        rows = list(session.exec(select(Asset).where(Asset.tenant_id == tenant_id)).all())
        if area_code:
            scoped_rows = [item for item in rows if item.region_code == area_code]
        else:
            scoped_rows = rows
        available = [
            item
            for item in scoped_rows
            if item.availability_status == AssetAvailabilityStatus.AVAILABLE
        ]
        return {
            "scope_area_code": area_code,
            "total_assets": len(scoped_rows),
            "available_assets": len(available),
        }

    def _score_candidates(
        self,
        session: Session,
        tenant_id: str,
        task: TaskCenterTask,
        candidates: list[User],
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        resource_snapshot = self._resource_snapshot(session, tenant_id, task.area_code)
        resource_available = int(resource_snapshot["available_assets"])
        resource_score = float(min(30, resource_available * 10))
        if resource_available == 0:
            resource_score = 5.0

        scored: list[dict[str, Any]] = []
        for candidate in candidates:
            workload = self._candidate_workload(session, tenant_id, candidate.id)
            workload_score = float(max(5, 40 - workload * 10))
            org_match = self._candidate_in_org_unit(session, tenant_id, candidate.id, task.org_unit_id)
            org_score = 30.0 if org_match else 0.0
            base_score = 20.0
            total = base_score + workload_score + org_score + resource_score
            reasons = [
                f"base={base_score}",
                f"workload={workload}=>{workload_score}",
                f"org_match={org_match}=>{org_score}",
                f"available_assets={resource_available}=>{resource_score}",
            ]
            scored.append(
                {
                    "user_id": candidate.id,
                    "total_score": total,
                    "breakdown": {
                        "base": base_score,
                        "workload": workload_score,
                        "org_match": org_score,
                        "resource_availability": resource_score,
                    },
                    "reasons": reasons,
                    "workload_count": workload,
                }
            )
        scored.sort(key=lambda item: (-float(item["total_score"]), int(item["workload_count"]), str(item["user_id"])))
        for item in scored:
            item.pop("workload_count", None)
        return scored, resource_snapshot

    def _ensure_scoped_mission(self, session: Session, tenant_id: str, mission_id: str) -> None:
        row = session.exec(
            select(Mission)
            .where(Mission.tenant_id == tenant_id)
            .where(Mission.id == mission_id)
        ).first()
        if row is None:
            raise NotFoundError("mission not found")

    def _record_history(
        self,
        session: Session,
        *,
        tenant_id: str,
        task_id: str,
        action: str,
        from_state: TaskCenterState | None,
        to_state: TaskCenterState | None,
        actor_id: str | None,
        note: str | None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        row = TaskCenterTaskHistory(
            tenant_id=tenant_id,
            task_id=task_id,
            action=action,
            from_state=from_state,
            to_state=to_state,
            actor_id=actor_id,
            note=note,
            detail=detail or {},
        )
        session.add(row)

    def _dispatch_task_internal(
        self,
        session: Session,
        *,
        row: TaskCenterTask,
        tenant_id: str,
        actor_id: str,
        assigned_to: str,
        dispatch_mode: TaskCenterDispatchMode,
        note: str | None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        if row.requires_approval and row.state != TaskCenterState.APPROVED:
            raise ConflictError("task requires approval before dispatch")
        if not can_task_center_transition(row.state, TaskCenterState.DISPATCHED):
            raise ConflictError(f"illegal transition: {row.state} -> {TaskCenterState.DISPATCHED}")
        self._ensure_scoped_user(session, tenant_id, assigned_to)

        source = row.state
        now = datetime.now(UTC)
        row.state = TaskCenterState.DISPATCHED
        row.dispatch_mode = dispatch_mode
        row.assigned_to = assigned_to
        row.dispatched_by = actor_id
        row.dispatched_at = now
        row.updated_at = now
        session.add(row)
        event_detail = {"assigned_to": assigned_to, "dispatch_mode": dispatch_mode}
        if detail is not None:
            event_detail.update(detail)
        self._record_history(
            session,
            tenant_id=tenant_id,
            task_id=row.id,
            action="dispatched",
            from_state=source,
            to_state=row.state,
            actor_id=actor_id,
            note=note,
            detail=event_detail,
        )

    def create_task_type(self, tenant_id: str, actor_id: str, payload: TaskTypeCatalogCreate) -> TaskTypeCatalog:
        with self._session() as session:
            row = TaskTypeCatalog(
                tenant_id=tenant_id,
                code=payload.code,
                name=payload.name,
                description=payload.description,
                is_active=payload.is_active,
                created_by=actor_id,
            )
            session.add(row)
            try:
                session.commit()
            except IntegrityError as exc:
                session.rollback()
                raise ConflictError("task type create conflict") from exc
            session.refresh(row)
            return row

    def list_task_types(self, tenant_id: str, *, is_active: bool | None = None) -> list[TaskTypeCatalog]:
        with self._session() as session:
            statement = select(TaskTypeCatalog).where(TaskTypeCatalog.tenant_id == tenant_id)
            if is_active is not None:
                statement = statement.where(TaskTypeCatalog.is_active == is_active)
            return list(session.exec(statement).all())

    def create_template(self, tenant_id: str, actor_id: str, payload: TaskTemplateCreate) -> TaskTemplate:
        with self._session() as session:
            _ = self._get_scoped_task_type(session, tenant_id, payload.task_type_id)
            row = TaskTemplate(
                tenant_id=tenant_id,
                task_type_id=payload.task_type_id,
                template_key=payload.template_key,
                name=payload.name,
                description=payload.description,
                requires_approval=payload.requires_approval,
                default_priority=payload.default_priority,
                default_risk_level=payload.default_risk_level,
                default_checklist=payload.default_checklist,
                default_payload=payload.default_payload,
                is_active=payload.is_active,
                created_by=actor_id,
            )
            session.add(row)
            try:
                session.commit()
            except IntegrityError as exc:
                session.rollback()
                raise ConflictError("task template create conflict") from exc
            session.refresh(row)
            return row

    def list_templates(
        self,
        tenant_id: str,
        *,
        task_type_id: str | None = None,
        is_active: bool | None = None,
    ) -> list[TaskTemplate]:
        with self._session() as session:
            statement = select(TaskTemplate).where(TaskTemplate.tenant_id == tenant_id)
            if task_type_id is not None:
                statement = statement.where(TaskTemplate.task_type_id == task_type_id)
            if is_active is not None:
                statement = statement.where(TaskTemplate.is_active == is_active)
            return list(session.exec(statement).all())

    def create_task(
        self,
        tenant_id: str,
        actor_id: str,
        payload: TaskCenterTaskCreate,
    ) -> TaskCenterTask:
        with self._session() as session:
            task_type = self._get_scoped_task_type(session, tenant_id, payload.task_type_id)
            if not task_type.is_active:
                raise ConflictError("task type is inactive")

            template: TaskTemplate | None = None
            if payload.template_id is not None:
                template = self._get_scoped_template(session, tenant_id, payload.template_id)
                if template.task_type_id != payload.task_type_id:
                    raise ConflictError("template does not match task type")
                if not template.is_active:
                    raise ConflictError("task template is inactive")

            if payload.org_unit_id is not None:
                self._ensure_scoped_org_unit(session, tenant_id, payload.org_unit_id)
            if payload.mission_id is not None:
                self._ensure_scoped_mission(session, tenant_id, payload.mission_id)

            requires_approval = (
                payload.requires_approval
                if payload.requires_approval is not None
                else (template.requires_approval if template is not None else False)
            )
            priority = payload.priority if payload.priority is not None else (
                template.default_priority if template is not None else 5
            )
            risk_level = payload.risk_level if payload.risk_level is not None else (
                template.default_risk_level if template is not None else 3
            )

            if not (1 <= priority <= 10):
                raise ConflictError("priority out of range")
            if not (1 <= risk_level <= 5):
                raise ConflictError("risk level out of range")

            checklist = (
                payload.checklist
                if "checklist" in payload.model_fields_set
                else (template.default_checklist if template is not None else [])
            )
            template_context = dict(template.default_payload) if template is not None else {}
            if "context_data" in payload.model_fields_set:
                context_data = {**template_context, **payload.context_data}
            else:
                context_data = template_context

            row = TaskCenterTask(
                tenant_id=tenant_id,
                task_type_id=payload.task_type_id,
                template_id=payload.template_id,
                mission_id=payload.mission_id,
                name=payload.name,
                description=payload.description,
                state=TaskCenterState.DRAFT,
                requires_approval=requires_approval,
                priority=priority,
                risk_level=risk_level,
                org_unit_id=payload.org_unit_id,
                project_code=payload.project_code,
                area_code=payload.area_code,
                area_geom=payload.area_geom,
                checklist=checklist,
                attachments=payload.attachments,
                context_data=context_data,
                created_by=actor_id,
            )
            session.add(row)
            self._record_history(
                session,
                tenant_id=tenant_id,
                task_id=row.id,
                action="created",
                from_state=None,
                to_state=TaskCenterState.DRAFT,
                actor_id=actor_id,
                note=None,
                detail={"task_type_id": row.task_type_id, "template_id": row.template_id},
            )
            try:
                session.commit()
            except IntegrityError as exc:
                session.rollback()
                raise ConflictError("task create conflict") from exc
            session.refresh(row)

        event_bus.publish_dict(
            "task_center.task.created",
            tenant_id,
            {"task_id": row.id, "state": row.state, "task_type_id": row.task_type_id},
        )
        return row

    def list_tasks(
        self,
        tenant_id: str,
        *,
        state: TaskCenterState | None = None,
        viewer_user_id: str | None = None,
    ) -> list[TaskCenterTask]:
        with self._session() as session:
            statement = select(TaskCenterTask).where(TaskCenterTask.tenant_id == tenant_id)
            if state is not None:
                statement = statement.where(TaskCenterTask.state == state)
            rows = list(session.exec(statement).all())
            if viewer_user_id is None:
                return rows
            scope = self._data_perimeter.resolve_scope(session, tenant_id, viewer_user_id)
            return [item for item in rows if self._data_perimeter.task_center_visible(item, scope)]

    def get_task(
        self,
        tenant_id: str,
        task_id: str,
        *,
        viewer_user_id: str | None = None,
    ) -> TaskCenterTask:
        with self._session() as session:
            row = self._get_scoped_task(session, tenant_id, task_id)
            self._ensure_visible(session, tenant_id, viewer_user_id, row)
            return row

    def submit_for_approval(
        self,
        tenant_id: str,
        task_id: str,
        actor_id: str,
        payload: TaskCenterTaskSubmitApprovalRequest,
        *,
        viewer_user_id: str | None = None,
    ) -> TaskCenterTask:
        with self._session() as session:
            row = self._get_scoped_task(session, tenant_id, task_id)
            self._ensure_visible(session, tenant_id, viewer_user_id, row)
            if not row.requires_approval:
                raise ConflictError("task does not require approval")
            if not can_task_center_transition(row.state, TaskCenterState.APPROVAL_PENDING):
                raise ConflictError(f"illegal transition: {row.state} -> {TaskCenterState.APPROVAL_PENDING}")

            source = row.state
            row.state = TaskCenterState.APPROVAL_PENDING
            row.updated_at = datetime.now(UTC)
            session.add(row)
            self._record_history(
                session,
                tenant_id=tenant_id,
                task_id=row.id,
                action="submitted_for_approval",
                from_state=source,
                to_state=row.state,
                actor_id=actor_id,
                note=payload.note,
            )
            session.commit()
            session.refresh(row)

        event_bus.publish_dict(
            "task_center.task.submitted_for_approval",
            tenant_id,
            {"task_id": row.id, "state": row.state},
        )
        return row

    def approve_task(
        self,
        tenant_id: str,
        task_id: str,
        actor_id: str,
        payload: TaskCenterTaskApproveRequest,
        *,
        viewer_user_id: str | None = None,
    ) -> TaskCenterTask:
        target_state = (
            TaskCenterState.APPROVED
            if payload.decision == ApprovalDecision.APPROVE
            else TaskCenterState.REJECTED
        )
        with self._session() as session:
            row = self._get_scoped_task(session, tenant_id, task_id)
            self._ensure_visible(session, tenant_id, viewer_user_id, row)
            if not row.requires_approval:
                raise ConflictError("task does not require approval")
            if not can_task_center_transition(row.state, target_state):
                raise ConflictError(f"illegal transition: {row.state} -> {target_state}")

            source = row.state
            row.state = target_state
            row.updated_at = datetime.now(UTC)
            session.add(row)
            self._record_history(
                session,
                tenant_id=tenant_id,
                task_id=row.id,
                action="approved" if target_state == TaskCenterState.APPROVED else "rejected",
                from_state=source,
                to_state=row.state,
                actor_id=actor_id,
                note=payload.note,
                detail={"decision": payload.decision},
            )
            session.commit()
            session.refresh(row)

        event_name = "task_center.task.approved" if target_state == TaskCenterState.APPROVED else "task_center.task.rejected"
        event_bus.publish_dict(
            event_name,
            tenant_id,
            {"task_id": row.id, "state": row.state},
        )
        return row

    def dispatch_task(
        self,
        tenant_id: str,
        task_id: str,
        actor_id: str,
        payload: TaskCenterTaskDispatchRequest,
        *,
        viewer_user_id: str | None = None,
    ) -> TaskCenterTask:
        with self._session() as session:
            row = self._get_scoped_task(session, tenant_id, task_id)
            self._ensure_visible(session, tenant_id, viewer_user_id, row)
            self._dispatch_task_internal(
                session,
                row=row,
                tenant_id=tenant_id,
                actor_id=actor_id,
                assigned_to=payload.assigned_to,
                dispatch_mode=TaskCenterDispatchMode.MANUAL,
                note=payload.note,
            )
            session.commit()
            session.refresh(row)

        event_bus.publish_dict(
            "task_center.task.dispatched",
            tenant_id,
            {"task_id": row.id, "state": row.state, "assigned_to": row.assigned_to},
        )
        return row

    def auto_dispatch_task(
        self,
        tenant_id: str,
        task_id: str,
        actor_id: str,
        payload: TaskCenterTaskAutoDispatchRequest,
        *,
        viewer_user_id: str | None = None,
    ) -> tuple[TaskCenterTask, list[dict[str, Any]], dict[str, Any]]:
        with self._session() as session:
            row = self._get_scoped_task(session, tenant_id, task_id)
            self._ensure_visible(session, tenant_id, viewer_user_id, row)
            candidates = self._list_candidate_users(session, tenant_id, payload.candidate_user_ids)
            if not candidates:
                raise ConflictError("no available candidates for auto dispatch")
            scores, resource_snapshot = self._score_candidates(session, tenant_id, row, candidates)
            selected_user_id = str(scores[0]["user_id"])

            self._dispatch_task_internal(
                session,
                row=row,
                tenant_id=tenant_id,
                actor_id=actor_id,
                assigned_to=selected_user_id,
                dispatch_mode=TaskCenterDispatchMode.AUTO,
                note=payload.note,
                detail={
                    "resource_snapshot": resource_snapshot,
                    "scores": scores,
                },
            )
            session.commit()
            session.refresh(row)

        event_bus.publish_dict(
            "task_center.task.auto_dispatched",
            tenant_id,
            {
                "task_id": row.id,
                "state": row.state,
                "selected_user_id": selected_user_id,
                "resource_snapshot": resource_snapshot,
            },
        )
        return row, scores, resource_snapshot

    def update_risk_checklist(
        self,
        tenant_id: str,
        task_id: str,
        actor_id: str,
        payload: TaskCenterRiskChecklistUpdateRequest,
        *,
        viewer_user_id: str | None = None,
    ) -> TaskCenterTask:
        with self._session() as session:
            row = self._get_scoped_task(session, tenant_id, task_id)
            self._ensure_visible(session, tenant_id, viewer_user_id, row)
            if row.state in {TaskCenterState.ARCHIVED, TaskCenterState.CANCELED}:
                raise ConflictError("cannot update risk/checklist on closed task")

            old_risk_level = row.risk_level
            old_checklist_count = len(row.checklist)

            if payload.risk_level is not None:
                row.risk_level = payload.risk_level
            if payload.checklist is not None:
                row.checklist = payload.checklist
            row.updated_at = datetime.now(UTC)
            session.add(row)
            self._record_history(
                session,
                tenant_id=tenant_id,
                task_id=row.id,
                action="risk_checklist_updated",
                from_state=row.state,
                to_state=row.state,
                actor_id=actor_id,
                note=payload.note,
                detail={
                    "old_risk_level": old_risk_level,
                    "new_risk_level": row.risk_level,
                    "old_checklist_count": old_checklist_count,
                    "new_checklist_count": len(row.checklist),
                },
            )
            session.commit()
            session.refresh(row)

        event_bus.publish_dict(
            "task_center.task.risk_checklist_updated",
            tenant_id,
            {"task_id": row.id, "risk_level": row.risk_level, "checklist_count": len(row.checklist)},
        )
        return row

    def add_attachment(
        self,
        tenant_id: str,
        task_id: str,
        actor_id: str,
        payload: TaskCenterAttachmentAddRequest,
        *,
        viewer_user_id: str | None = None,
    ) -> TaskCenterTask:
        with self._session() as session:
            row = self._get_scoped_task(session, tenant_id, task_id)
            self._ensure_visible(session, tenant_id, viewer_user_id, row)
            attachment = {
                "id": str(uuid4()),
                "name": payload.name,
                "url": payload.url,
                "media_type": payload.media_type,
                "size_bytes": payload.size_bytes,
                "note": payload.note,
                "created_by": actor_id,
                "created_at": datetime.now(UTC).isoformat(),
            }
            row.attachments = [*row.attachments, attachment]
            row.updated_at = datetime.now(UTC)
            session.add(row)
            self._record_history(
                session,
                tenant_id=tenant_id,
                task_id=row.id,
                action="attachment_added",
                from_state=row.state,
                to_state=row.state,
                actor_id=actor_id,
                note=payload.note,
                detail={"attachment_id": attachment["id"], "name": payload.name},
            )
            session.commit()
            session.refresh(row)

        event_bus.publish_dict(
            "task_center.task.attachment_added",
            tenant_id,
            {"task_id": row.id, "attachment_id": attachment["id"]},
        )
        return row

    def add_comment(
        self,
        tenant_id: str,
        task_id: str,
        actor_id: str,
        payload: TaskCenterCommentCreateRequest,
        *,
        viewer_user_id: str | None = None,
    ) -> dict[str, Any]:
        with self._session() as session:
            row = self._get_scoped_task(session, tenant_id, task_id)
            self._ensure_visible(session, tenant_id, viewer_user_id, row)
            comment = {
                "id": str(uuid4()),
                "content": payload.content,
                "created_by": actor_id,
                "created_at": datetime.now(UTC).isoformat(),
            }
            current_context = dict(row.context_data)
            current_comments = current_context.get("comments", [])
            comments = [item for item in current_comments if isinstance(item, dict)]
            comments.append(comment)
            current_context["comments"] = comments
            row.context_data = current_context
            row.updated_at = datetime.now(UTC)
            session.add(row)
            self._record_history(
                session,
                tenant_id=tenant_id,
                task_id=row.id,
                action="comment_added",
                from_state=row.state,
                to_state=row.state,
                actor_id=actor_id,
                note=None,
                detail={"comment_id": comment["id"]},
            )
            session.commit()
            session.refresh(row)

        event_bus.publish_dict(
            "task_center.task.comment_added",
            tenant_id,
            {"task_id": row.id, "comment_id": comment["id"]},
        )
        return comment

    def list_comments(
        self,
        tenant_id: str,
        task_id: str,
        *,
        viewer_user_id: str | None = None,
    ) -> list[dict[str, Any]]:
        with self._session() as session:
            row = self._get_scoped_task(session, tenant_id, task_id)
            self._ensure_visible(session, tenant_id, viewer_user_id, row)
            current_comments = row.context_data.get("comments", [])
            comments = [item for item in current_comments if isinstance(item, dict)]
            return sorted(comments, key=lambda item: str(item.get("created_at", "")))

    def transition_task(
        self,
        tenant_id: str,
        task_id: str,
        actor_id: str,
        payload: TaskCenterTaskTransitionRequest,
        *,
        viewer_user_id: str | None = None,
    ) -> TaskCenterTask:
        if payload.target_state in {
            TaskCenterState.APPROVAL_PENDING,
            TaskCenterState.APPROVED,
            TaskCenterState.REJECTED,
            TaskCenterState.DISPATCHED,
        }:
            raise ConflictError("target state requires dedicated endpoint")

        with self._session() as session:
            row = self._get_scoped_task(session, tenant_id, task_id)
            self._ensure_visible(session, tenant_id, viewer_user_id, row)
            if not can_task_center_transition(row.state, payload.target_state):
                raise ConflictError(f"illegal transition: {row.state} -> {payload.target_state}")
            if payload.target_state == TaskCenterState.IN_PROGRESS and row.assigned_to is None:
                raise ConflictError("task must be dispatched before IN_PROGRESS")

            source = row.state
            now = datetime.now(UTC)
            row.state = payload.target_state
            row.updated_at = now
            if payload.target_state == TaskCenterState.IN_PROGRESS and row.started_at is None:
                row.started_at = now
            if payload.target_state == TaskCenterState.ACCEPTED:
                row.accepted_at = now
            if payload.target_state == TaskCenterState.ARCHIVED:
                row.archived_at = now
            if payload.target_state == TaskCenterState.CANCELED:
                row.canceled_at = now

            session.add(row)
            self._record_history(
                session,
                tenant_id=tenant_id,
                task_id=row.id,
                action="state_changed",
                from_state=source,
                to_state=row.state,
                actor_id=actor_id,
                note=payload.note,
            )
            session.commit()
            session.refresh(row)

        event_bus.publish_dict(
            "task_center.task.state_changed",
            tenant_id,
            {"task_id": row.id, "state": row.state},
        )
        return row

    def list_history(
        self,
        tenant_id: str,
        task_id: str,
        *,
        viewer_user_id: str | None = None,
    ) -> list[TaskCenterTaskHistory]:
        with self._session() as session:
            task = self._get_scoped_task(session, tenant_id, task_id)
            self._ensure_visible(session, tenant_id, viewer_user_id, task)
            statement = (
                select(TaskCenterTaskHistory)
                .where(TaskCenterTaskHistory.tenant_id == tenant_id)
                .where(TaskCenterTaskHistory.task_id == task_id)
            )
            rows = list(session.exec(statement).all())
            return sorted(rows, key=lambda item: item.created_at)
