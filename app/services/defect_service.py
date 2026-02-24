from __future__ import annotations

from typing import ClassVar

from sqlmodel import Session, select

from app.domain.models import (
    Defect,
    DefectAction,
    DefectAssignRequest,
    DefectStatsRead,
    DefectStatus,
    DefectStatusRequest,
    InspectionObservation,
    InspectionTask,
    InspectionTaskStatus,
)
from app.infra.db import get_engine
from app.infra.events import event_bus


class DefectError(Exception):
    pass


class NotFoundError(DefectError):
    pass


class ConflictError(DefectError):
    pass


class DefectService:
    _allowed_transitions: ClassVar[dict[DefectStatus, set[DefectStatus]]] = {
        DefectStatus.OPEN: {DefectStatus.ASSIGNED},
        DefectStatus.ASSIGNED: {DefectStatus.IN_PROGRESS},
        DefectStatus.IN_PROGRESS: {DefectStatus.FIXED},
        DefectStatus.FIXED: {DefectStatus.VERIFIED},
        DefectStatus.VERIFIED: {DefectStatus.CLOSED},
        DefectStatus.CLOSED: set(),
    }

    def _session(self) -> Session:
        return Session(get_engine(), expire_on_commit=False)

    def _get_scoped_observation(
        self,
        session: Session,
        tenant_id: str,
        observation_id: str,
    ) -> InspectionObservation:
        observation = self._find_scoped_observation(session, tenant_id, observation_id)
        if observation is None:
            raise NotFoundError("observation not found")
        return observation

    def _find_scoped_observation(
        self,
        session: Session,
        tenant_id: str,
        observation_id: str,
    ) -> InspectionObservation | None:
        return session.exec(
            select(InspectionObservation)
            .where(InspectionObservation.tenant_id == tenant_id)
            .where(InspectionObservation.id == observation_id)
        ).first()

    def _get_scoped_defect(self, session: Session, tenant_id: str, defect_id: str) -> Defect:
        defect = session.exec(
            select(Defect)
            .where(Defect.tenant_id == tenant_id)
            .where(Defect.id == defect_id)
        ).first()
        if defect is None:
            raise NotFoundError("defect not found")
        return defect

    def _find_scoped_task(self, session: Session, tenant_id: str, task_id: str) -> InspectionTask | None:
        return session.exec(
            select(InspectionTask)
            .where(InspectionTask.tenant_id == tenant_id)
            .where(InspectionTask.id == task_id)
        ).first()

    def _create_action(self, session: Session, tenant_id: str, defect_id: str, action_type: str, note: str) -> None:
        action = DefectAction(
            tenant_id=tenant_id,
            defect_id=defect_id,
            action_type=action_type,
            note=note,
        )
        session.add(action)

    def create_from_observation(self, tenant_id: str, observation_id: str) -> Defect:
        with self._session() as session:
            observation = self._get_scoped_observation(session, tenant_id, observation_id)

            existing = session.exec(
                select(Defect)
                .where(Defect.tenant_id == tenant_id)
                .where(Defect.observation_id == observation_id)
            ).first()
            if existing is not None:
                return existing

            defect = Defect(
                tenant_id=tenant_id,
                observation_id=observation_id,
                title=f"Defect for item {observation.item_code}",
                description=observation.note,
                severity=observation.severity,
                status=DefectStatus.OPEN,
            )
            session.add(defect)
            session.commit()
            session.refresh(defect)
            self._create_action(
                session,
                tenant_id,
                defect.id,
                "CREATED_FROM_OBSERVATION",
                f"observation_id={observation_id}",
            )
            session.commit()

        event_bus.publish_dict(
            "defect.created",
            tenant_id,
            {"defect_id": defect.id, "observation_id": defect.observation_id, "status": defect.status},
        )
        return defect

    def list_defects(
        self,
        tenant_id: str,
        status: DefectStatus | None = None,
        assigned_to: str | None = None,
    ) -> list[Defect]:
        with self._session() as session:
            statement = select(Defect).where(Defect.tenant_id == tenant_id)
            if status is not None:
                statement = statement.where(Defect.status == status)
            if assigned_to is not None:
                statement = statement.where(Defect.assigned_to == assigned_to)
            return list(session.exec(statement).all())

    def get_defect(self, tenant_id: str, defect_id: str) -> tuple[Defect, list[DefectAction]]:
        with self._session() as session:
            defect = self._get_scoped_defect(session, tenant_id, defect_id)
            actions = list(
                session.exec(
                    select(DefectAction)
                    .where(DefectAction.tenant_id == tenant_id)
                    .where(DefectAction.defect_id == defect_id)
                ).all()
            )
            return defect, actions

    def assign_defect(self, tenant_id: str, defect_id: str, payload: DefectAssignRequest) -> Defect:
        with self._session() as session:
            defect = self._get_scoped_defect(session, tenant_id, defect_id)
            if defect.status == DefectStatus.CLOSED:
                raise ConflictError("closed defect cannot be assigned")
            defect.assigned_to = payload.assigned_to
            defect.status = DefectStatus.ASSIGNED
            session.add(defect)
            note = payload.note or f"assigned_to={payload.assigned_to}"
            self._create_action(session, tenant_id, defect.id, "ASSIGNED", note)
            session.commit()
            session.refresh(defect)

        event_bus.publish_dict(
            "defect.assigned",
            tenant_id,
            {"defect_id": defect.id, "assigned_to": defect.assigned_to},
        )
        return defect

    def update_status(self, tenant_id: str, defect_id: str, payload: DefectStatusRequest) -> Defect:
        with self._session() as session:
            defect = self._get_scoped_defect(session, tenant_id, defect_id)
            if defect.status == payload.status:
                return defect
            allowed = self._allowed_transitions.get(defect.status, set())
            if payload.status not in allowed:
                raise ConflictError(f"illegal transition: {defect.status} -> {payload.status}")

            defect.status = payload.status
            session.add(defect)
            note = payload.note or ""
            self._create_action(session, tenant_id, defect.id, f"STATUS_{payload.status}", note)

            if payload.status == DefectStatus.FIXED:
                observation = self._find_scoped_observation(session, tenant_id, defect.observation_id)
                if observation is not None:
                    review_task = InspectionTask(
                        tenant_id=tenant_id,
                        name=f"Review-{defect.id[:8]}",
                        template_id=self._resolve_template_id_for_review(session, tenant_id, observation.task_id),
                        mission_id=None,
                        area_geom="",
                        priority=2,
                        status=InspectionTaskStatus.SCHEDULED,
                    )
                    session.add(review_task)
                    self._create_action(
                        session,
                        tenant_id,
                        defect.id,
                        "REVIEW_TASK_CREATED",
                        "auto-created on FIXED",
                    )

            session.commit()
            session.refresh(defect)

        event_bus.publish_dict(
            "defect.status_changed",
            tenant_id,
            {"defect_id": defect.id, "status": defect.status},
        )
        return defect

    def _resolve_template_id_for_review(self, session: Session, tenant_id: str, task_id: str) -> str:
        source_task = self._find_scoped_task(session, tenant_id, task_id)
        if source_task is not None:
            return source_task.template_id
        fallback = session.exec(select(InspectionTask).where(InspectionTask.tenant_id == tenant_id)).first()
        if fallback is None:
            raise ConflictError("cannot create review task without any inspection task template")
        return fallback.template_id

    def stats(self, tenant_id: str) -> DefectStatsRead:
        rows = self.list_defects(tenant_id)
        by_status: dict[str, int] = {}
        for row in rows:
            key = row.status.value
            by_status[key] = by_status.get(key, 0) + 1
        total = len(rows)
        closed = by_status.get(DefectStatus.CLOSED.value, 0)
        closure_rate = (closed / total) if total else 0.0
        return DefectStatsRead(
            total=total,
            closed=closed,
            by_status=by_status,
            closure_rate=closure_rate,
        )
