from __future__ import annotations

from sqlmodel import Session, select

from app.domain.models import (
    Incident,
    IncidentCreate,
    IncidentCreateTaskRead,
    IncidentCreateTaskRequest,
    IncidentStatus,
    InspectionTask,
    InspectionTaskStatus,
    InspectionTemplate,
    Mission,
    MissionPlanType,
)
from app.domain.state_machine import MissionState
from app.infra.db import get_engine
from app.infra.events import event_bus


class IncidentError(Exception):
    pass


class NotFoundError(IncidentError):
    pass


class ConflictError(IncidentError):
    pass


class IncidentService:
    def _session(self) -> Session:
        return Session(get_engine(), expire_on_commit=False)

    def _get_scoped_incident(
        self,
        session: Session,
        tenant_id: str,
        incident_id: str,
    ) -> Incident | None:
        return session.exec(
            select(Incident)
            .where(Incident.tenant_id == tenant_id)
            .where(Incident.id == incident_id)
        ).first()

    def create_incident(self, tenant_id: str, payload: IncidentCreate) -> Incident:
        with self._session() as session:
            incident = Incident(
                tenant_id=tenant_id,
                title=payload.title,
                level=payload.level,
                location_geom=payload.location_geom,
                status=IncidentStatus.OPEN,
            )
            session.add(incident)
            session.commit()
            session.refresh(incident)
        event_bus.publish_dict(
            "incident.created",
            tenant_id,
            {"incident_id": incident.id, "level": incident.level, "status": incident.status},
        )
        return incident

    def list_incidents(self, tenant_id: str) -> list[Incident]:
        with self._session() as session:
            statement = select(Incident).where(Incident.tenant_id == tenant_id)
            return list(session.exec(statement).all())

    def create_task_for_incident(
        self,
        tenant_id: str,
        actor_id: str,
        incident_id: str,
        payload: IncidentCreateTaskRequest,
    ) -> IncidentCreateTaskRead:
        with self._session() as session:
            incident = self._get_scoped_incident(session, tenant_id, incident_id)
            if incident is None:
                raise NotFoundError("incident not found")
            if incident.status == IncidentStatus.TASK_CREATED and incident.linked_task_id is not None:
                raise ConflictError("incident task already created")

            template_id = payload.template_id or self._resolve_template(session, tenant_id)
            mission = Mission(
                tenant_id=tenant_id,
                name=f"Emergency-{incident.title}",
                drone_id=None,
                plan_type=MissionPlanType.POINT_TASK,
                payload={"incident_id": incident.id, "location": incident.location_geom},
                constraints={"priority": "P0", "emergency_mode": True},
                state=MissionState.DRAFT,
                created_by=actor_id,
            )
            session.add(mission)
            session.commit()
            session.refresh(mission)

            task = InspectionTask(
                tenant_id=tenant_id,
                name=payload.task_name or f"EmergencyTask-{incident.id[:8]}",
                template_id=template_id,
                mission_id=mission.id,
                area_geom=incident.location_geom,
                priority=1,
                status=InspectionTaskStatus.SCHEDULED,
            )
            session.add(task)
            session.commit()
            session.refresh(task)

            incident.status = IncidentStatus.TASK_CREATED
            incident.linked_task_id = task.id
            session.add(incident)
            session.commit()

        event_bus.publish_dict(
            "incident.task_created",
            tenant_id,
            {"incident_id": incident.id, "mission_id": mission.id, "task_id": task.id},
        )
        return IncidentCreateTaskRead(
            incident_id=incident.id,
            mission_id=mission.id,
            task_id=task.id,
        )

    def _resolve_template(self, session: Session, tenant_id: str) -> str:
        template = session.exec(
            select(InspectionTemplate)
            .where(InspectionTemplate.tenant_id == tenant_id)
            .where(InspectionTemplate.is_active == True)  # noqa: E712
        ).first()
        if template is None:
            raise ConflictError("no active inspection template for emergency task creation")
        return template.id
