from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.domain.models import (
    Approval,
    ApprovalDecision,
    Drone,
    Mission,
    MissionApprovalRequest,
    MissionCreate,
    MissionRun,
    MissionTransitionRequest,
    MissionUpdate,
    OrgUnit,
)
from app.domain.permissions import PERM_MISSION_FASTLANE, PERM_WILDCARD
from app.domain.state_machine import MissionState, can_transition
from app.infra.db import get_engine
from app.infra.events import event_bus
from app.services.compliance_service import ComplianceService
from app.services.data_perimeter_service import DataPerimeterService


class MissionError(Exception):
    pass


class NotFoundError(MissionError):
    pass


class ConflictError(MissionError):
    pass


class PermissionDeniedError(MissionError):
    pass


class MissionService:
    def __init__(self) -> None:
        self._data_perimeter = DataPerimeterService()
        self._compliance = ComplianceService()

    def _session(self) -> Session:
        return Session(get_engine(), expire_on_commit=False)

    def _get_scoped_mission(self, session: Session, tenant_id: str, mission_id: str) -> Mission:
        mission = session.exec(
            select(Mission).where(Mission.tenant_id == tenant_id).where(Mission.id == mission_id)
        ).first()
        if mission is None:
            raise NotFoundError("mission not found")
        return mission

    def _ensure_scoped_drone(self, session: Session, tenant_id: str, drone_id: str) -> None:
        drone = session.exec(select(Drone).where(Drone.tenant_id == tenant_id).where(Drone.id == drone_id)).first()
        if drone is None:
            raise NotFoundError("drone not found")

    def _ensure_scoped_org_unit(self, session: Session, tenant_id: str, org_unit_id: str) -> None:
        org_unit = session.exec(
            select(OrgUnit).where(OrgUnit.tenant_id == tenant_id).where(OrgUnit.id == org_unit_id)
        ).first()
        if org_unit is None:
            raise NotFoundError("org unit not found")

    def _has_permission(self, permissions: list[str], required: str) -> bool:
        return required in permissions or PERM_WILDCARD in permissions

    def _ensure_mission_visible(
        self,
        session: Session,
        tenant_id: str,
        viewer_user_id: str | None,
        mission: Mission,
    ) -> None:
        if viewer_user_id is None:
            return
        scope = self._data_perimeter.resolve_scope(session, tenant_id, viewer_user_id)
        if not self._data_perimeter.mission_visible(mission, scope):
            raise NotFoundError("mission not found")

    def _enforce_fastlane(
        self,
        *,
        constraints: dict[str, object],
        permissions: list[str],
        actor_id: str,
    ) -> dict[str, object]:
        emergency = bool(constraints.get("emergency_fastlane", False))
        if not emergency:
            return constraints
        if not self._has_permission(permissions, PERM_MISSION_FASTLANE):
            raise PermissionDeniedError(f"Missing permission: {PERM_MISSION_FASTLANE}")
        enriched = dict(constraints)
        enriched["emergency_fastlane"] = True
        enriched["fastlane_authorized_by"] = actor_id
        enriched["fastlane_authorized_at"] = datetime.now(UTC).isoformat()
        return enriched

    def create_mission(
        self,
        tenant_id: str,
        actor_id: str,
        permissions: list[str],
        payload: MissionCreate,
    ) -> Mission:
        with self._session() as session:
            constraints = self._enforce_fastlane(
                constraints=payload.constraints,
                permissions=permissions,
                actor_id=actor_id,
            )
            self._compliance.validate_mission_plan(
                session=session,
                tenant_id=tenant_id,
                plan_type=payload.type,
                payload=payload.payload,
                constraints=constraints,
                area_code=payload.area_code,
            )
            if payload.drone_id is not None:
                self._ensure_scoped_drone(session, tenant_id, payload.drone_id)
            if payload.org_unit_id is not None:
                self._ensure_scoped_org_unit(session, tenant_id, payload.org_unit_id)
            mission = Mission(
                tenant_id=tenant_id,
                name=payload.name,
                drone_id=payload.drone_id,
                org_unit_id=payload.org_unit_id,
                project_code=payload.project_code,
                area_code=payload.area_code,
                plan_type=payload.type,
                payload=payload.payload,
                constraints=constraints,
                created_by=actor_id,
                state=MissionState.DRAFT,
            )
            session.add(mission)
            try:
                session.commit()
            except IntegrityError as exc:
                session.rollback()
                raise ConflictError("mission create conflict") from exc
            session.refresh(mission)

        event_bus.publish_dict(
            "mission.created",
            tenant_id,
            {"mission_id": mission.id, "state": mission.state, "name": mission.name},
        )
        return mission

    def list_missions(self, tenant_id: str, viewer_user_id: str | None = None) -> list[Mission]:
        with self._session() as session:
            rows = list(session.exec(select(Mission).where(Mission.tenant_id == tenant_id)).all())
            if viewer_user_id is None:
                return rows
            scope = self._data_perimeter.resolve_scope(session, tenant_id, viewer_user_id)
            return [item for item in rows if self._data_perimeter.mission_visible(item, scope)]

    def get_mission(self, tenant_id: str, mission_id: str, viewer_user_id: str | None = None) -> Mission:
        with self._session() as session:
            mission = self._get_scoped_mission(session, tenant_id, mission_id)
            self._ensure_mission_visible(session, tenant_id, viewer_user_id, mission)
            return mission

    def update_mission(
        self,
        tenant_id: str,
        mission_id: str,
        actor_id: str,
        permissions: list[str],
        payload: MissionUpdate,
        viewer_user_id: str | None = None,
    ) -> Mission:
        with self._session() as session:
            mission = self._get_scoped_mission(session, tenant_id, mission_id)
            self._ensure_mission_visible(session, tenant_id, viewer_user_id, mission)
            if mission.state not in {MissionState.DRAFT, MissionState.REJECTED}:
                raise ConflictError("mission can only be edited in DRAFT/REJECTED state")
            next_name = mission.name
            next_drone_id = mission.drone_id
            next_org_unit_id = mission.org_unit_id
            next_project_code = mission.project_code
            next_area_code = mission.area_code
            next_payload = mission.payload
            next_constraints = mission.constraints
            if payload.name is not None:
                next_name = payload.name
            if payload.drone_id is not None:
                self._ensure_scoped_drone(session, tenant_id, payload.drone_id)
                next_drone_id = payload.drone_id
            if payload.org_unit_id is not None:
                self._ensure_scoped_org_unit(session, tenant_id, payload.org_unit_id)
                next_org_unit_id = payload.org_unit_id
            if payload.project_code is not None:
                next_project_code = payload.project_code
            if payload.area_code is not None:
                next_area_code = payload.area_code
            if payload.payload is not None:
                next_payload = payload.payload
            if payload.constraints is not None:
                next_constraints = self._enforce_fastlane(
                    constraints=payload.constraints,
                    permissions=permissions,
                    actor_id=actor_id,
                )
            self._compliance.validate_mission_plan(
                session=session,
                tenant_id=tenant_id,
                plan_type=mission.plan_type,
                payload=next_payload,
                constraints=next_constraints,
                area_code=next_area_code,
            )
            mission.name = next_name
            mission.drone_id = next_drone_id
            mission.org_unit_id = next_org_unit_id
            mission.project_code = next_project_code
            mission.area_code = next_area_code
            mission.payload = next_payload
            mission.constraints = next_constraints
            mission.updated_at = datetime.now(UTC)
            session.add(mission)
            session.commit()
            session.refresh(mission)

        event_bus.publish_dict(
            "mission.updated",
            tenant_id,
            {"mission_id": mission.id, "state": mission.state},
        )
        return mission

    def delete_mission(self, tenant_id: str, mission_id: str, viewer_user_id: str | None = None) -> None:
        with self._session() as session:
            mission = self._get_scoped_mission(session, tenant_id, mission_id)
            self._ensure_mission_visible(session, tenant_id, viewer_user_id, mission)
            if mission.state not in {MissionState.DRAFT, MissionState.REJECTED}:
                raise ConflictError("mission can only be deleted in DRAFT/REJECTED state")
            session.delete(mission)
            session.commit()

    def approve_mission(
        self,
        tenant_id: str,
        mission_id: str,
        actor_id: str,
        payload: MissionApprovalRequest,
        viewer_user_id: str | None = None,
    ) -> tuple[Mission, Approval]:
        with self._session() as session:
            mission = self._get_scoped_mission(session, tenant_id, mission_id)
            self._ensure_mission_visible(session, tenant_id, viewer_user_id, mission)
            target_state = (
                MissionState.APPROVED
                if payload.decision == ApprovalDecision.APPROVE
                else MissionState.REJECTED
            )
            if not can_transition(mission.state, target_state):
                raise ConflictError(f"illegal transition: {mission.state} -> {target_state}")
            approval = Approval(
                tenant_id=tenant_id,
                mission_id=mission_id,
                approver_id=actor_id,
                decision=payload.decision,
                comment=payload.comment,
            )
            mission.state = target_state
            mission.updated_at = datetime.now(UTC)
            session.add(approval)
            session.add(mission)
            session.commit()
            session.refresh(approval)
            session.refresh(mission)

        event_name = "mission.approved" if target_state == MissionState.APPROVED else "mission.rejected"
        event_bus.publish_dict(
            event_name,
            tenant_id,
            {"mission_id": mission.id, "state": mission.state, "approval_id": approval.id},
        )
        return mission, approval

    def list_approvals(
        self,
        tenant_id: str,
        mission_id: str,
        viewer_user_id: str | None = None,
    ) -> list[Approval]:
        with self._session() as session:
            mission = self._get_scoped_mission(session, tenant_id, mission_id)
            self._ensure_mission_visible(session, tenant_id, viewer_user_id, mission)
            statement = select(Approval).where(Approval.tenant_id == tenant_id).where(
                Approval.mission_id == mission_id
            )
            return list(session.exec(statement).all())

    def transition_mission(
        self,
        tenant_id: str,
        mission_id: str,
        actor_id: str,
        permissions: list[str],
        payload: MissionTransitionRequest,
        viewer_user_id: str | None = None,
    ) -> Mission:
        with self._session() as session:
            mission = self._get_scoped_mission(session, tenant_id, mission_id)
            self._ensure_mission_visible(session, tenant_id, viewer_user_id, mission)
            if not can_transition(mission.state, payload.target_state):
                raise ConflictError(f"illegal transition: {mission.state} -> {payload.target_state}")
            if mission.constraints.get("emergency_fastlane", False) and payload.target_state == MissionState.RUNNING:
                self._enforce_fastlane(
                    constraints=mission.constraints,
                    permissions=permissions,
                    actor_id=actor_id,
                )
            if payload.target_state == MissionState.RUNNING:
                self._compliance.enforce_before_mission_run(
                    session=session,
                    tenant_id=tenant_id,
                    mission=mission,
                )

            mission.state = payload.target_state
            mission.updated_at = datetime.now(UTC)
            session.add(mission)

            if payload.target_state == MissionState.RUNNING:
                run = MissionRun(
                    tenant_id=tenant_id,
                    mission_id=mission_id,
                    state=MissionState.RUNNING,
                    started_at=datetime.now(UTC),
                )
                session.add(run)

            if payload.target_state in {MissionState.COMPLETED, MissionState.ABORTED}:
                runs = session.exec(
                    select(MissionRun)
                    .where(MissionRun.tenant_id == tenant_id)
                    .where(MissionRun.mission_id == mission_id)
                ).all()
                active_runs = [run for run in runs if run.ended_at is None]
                for run in active_runs:
                    run.state = payload.target_state
                    run.ended_at = datetime.now(UTC)
                    session.add(run)

            session.commit()
            session.refresh(mission)

        event_bus.publish_dict(
            "mission.state_changed",
            tenant_id,
            {"mission_id": mission.id, "state": mission.state},
        )
        return mission
