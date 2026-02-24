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
    OrgUnit,
)
from app.domain.state_machine import MissionState
from app.infra.db import get_engine
from app.infra.events import event_bus
from app.services.data_perimeter_service import DataPerimeterService


class IncidentError(Exception):
    pass


class NotFoundError(IncidentError):
    pass


class ConflictError(IncidentError):
    pass


class IncidentService:
    def __init__(self) -> None:
        self._data_perimeter = DataPerimeterService()

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

    def _ensure_incident_visible(
        self,
        session: Session,
        tenant_id: str,
        viewer_user_id: str | None,
        incident: Incident,
    ) -> None:
        if viewer_user_id is None:
            return
        scope = self._data_perimeter.resolve_scope(session, tenant_id, viewer_user_id)
        if not self._data_perimeter.incident_visible(incident, scope):
            raise NotFoundError("incident not found")

    def _ensure_scoped_org_unit(self, session: Session, tenant_id: str, org_unit_id: str) -> None:
        org_unit = session.exec(
            select(OrgUnit).where(OrgUnit.tenant_id == tenant_id).where(OrgUnit.id == org_unit_id)
        ).first()
        if org_unit is None:
            raise NotFoundError("org unit not found")

    def create_incident(self, tenant_id: str, payload: IncidentCreate) -> Incident:
        with self._session() as session:
            if payload.org_unit_id is not None:
                self._ensure_scoped_org_unit(session, tenant_id, payload.org_unit_id)
            incident = Incident(
                tenant_id=tenant_id,
                title=payload.title,
                level=payload.level,
                org_unit_id=payload.org_unit_id,
                project_code=payload.project_code,
                area_code=payload.area_code,
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

    def list_incidents(self, tenant_id: str, viewer_user_id: str | None = None) -> list[Incident]:
        with self._session() as session:
            rows = list(session.exec(select(Incident).where(Incident.tenant_id == tenant_id)).all())
            if viewer_user_id is None:
                return rows
            scope = self._data_perimeter.resolve_scope(session, tenant_id, viewer_user_id)
            return [item for item in rows if self._data_perimeter.incident_visible(item, scope)]

    def create_task_for_incident(
        self,
        tenant_id: str,
        actor_id: str,
        incident_id: str,
        payload: IncidentCreateTaskRequest,
        viewer_user_id: str | None = None,
    ) -> IncidentCreateTaskRead:
        with self._session() as session:
            incident = self._get_scoped_incident(session, tenant_id, incident_id)
            if incident is None:
                raise NotFoundError("incident not found")
            self._ensure_incident_visible(session, tenant_id, viewer_user_id, incident)
            if incident.status == IncidentStatus.TASK_CREATED and incident.linked_task_id is not None:
                raise ConflictError("incident task already created")

            template_id = payload.template_id or self._resolve_template(session, tenant_id)
            mission = Mission(
                tenant_id=tenant_id,
                name=f"Emergency-{incident.title}",
                drone_id=None,
                org_unit_id=incident.org_unit_id,
                project_code=incident.project_code,
                area_code=incident.area_code,
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
                org_unit_id=incident.org_unit_id,
                project_code=incident.project_code,
                area_code=incident.area_code,
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
