from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import true
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.domain.models import (
    AirspacePolicyEffect,
    AirspacePolicyLayer,
    AirspaceZone,
    AirspaceZoneCreate,
    AirspaceZoneType,
    ApprovalFlowAction,
    ApprovalFlowInstanceStatus,
    ApprovalRecord,
    ApprovalRecordCreate,
    CommandType,
    ComplianceApprovalFlowInstance,
    ComplianceApprovalFlowInstanceActionRequest,
    ComplianceApprovalFlowInstanceCreate,
    ComplianceApprovalFlowTemplate,
    ComplianceApprovalFlowTemplateCreate,
    ComplianceDecision,
    ComplianceDecisionRecord,
    ComplianceReasonCode,
    Mission,
    MissionPlanType,
    MissionPreflightChecklist,
    MissionPreflightChecklistInitRequest,
    MissionPreflightChecklistItemCheckRequest,
    OrgUnit,
    PreflightChecklistStatus,
    PreflightChecklistTemplate,
    PreflightChecklistTemplateCreate,
)
from app.domain.state_machine import MissionState, can_transition
from app.infra.db import get_engine

POLYGON_WKT_PATTERN = re.compile(r"^POLYGON\s*\(\((.+)\)\)$", re.IGNORECASE)


class ComplianceError(Exception):
    pass


class NotFoundError(ComplianceError):
    pass


class ConflictError(ComplianceError):
    pass


class ComplianceViolationError(ConflictError):
    def __init__(
        self,
        reason_code: ComplianceReasonCode,
        message: str,
        detail: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.reason_code = reason_code
        self.detail = detail or {}


@dataclass(frozen=True)
class _Point:
    lat: float
    lon: float
    alt_m: float | None = None


class ComplianceService:
    def _session(self) -> Session:
        return Session(get_engine(), expire_on_commit=False)

    def _get_scoped_mission(self, session: Session, tenant_id: str, mission_id: str) -> Mission:
        mission = session.exec(
            select(Mission)
            .where(Mission.tenant_id == tenant_id)
            .where(Mission.id == mission_id)
        ).first()
        if mission is None:
            raise NotFoundError("mission not found")
        return mission

    def _get_scoped_zone(self, session: Session, tenant_id: str, zone_id: str) -> AirspaceZone:
        zone = session.exec(
            select(AirspaceZone)
            .where(AirspaceZone.tenant_id == tenant_id)
            .where(AirspaceZone.id == zone_id)
        ).first()
        if zone is None:
            raise NotFoundError("airspace zone not found")
        return zone

    def _get_scoped_org_unit(self, session: Session, tenant_id: str, org_unit_id: str) -> OrgUnit:
        row = session.exec(
            select(OrgUnit)
            .where(OrgUnit.tenant_id == tenant_id)
            .where(OrgUnit.id == org_unit_id)
        ).first()
        if row is None:
            raise NotFoundError("org unit not found")
        return row

    def _get_scoped_template(
        self,
        session: Session,
        tenant_id: str,
        template_id: str,
    ) -> PreflightChecklistTemplate:
        row = session.exec(
            select(PreflightChecklistTemplate)
            .where(PreflightChecklistTemplate.tenant_id == tenant_id)
            .where(PreflightChecklistTemplate.id == template_id)
        ).first()
        if row is None:
            raise NotFoundError("preflight checklist template not found")
        return row

    def _get_scoped_preflight_by_mission(
        self,
        session: Session,
        tenant_id: str,
        mission_id: str,
    ) -> MissionPreflightChecklist:
        row = session.exec(
            select(MissionPreflightChecklist)
            .where(MissionPreflightChecklist.tenant_id == tenant_id)
            .where(MissionPreflightChecklist.mission_id == mission_id)
        ).first()
        if row is None:
            raise NotFoundError("mission preflight checklist not found")
        return row

    def _parse_polygon_wkt(self, value: str) -> list[tuple[float, float]]:
        match = POLYGON_WKT_PATTERN.match(value.strip())
        if match is None:
            raise ConflictError("invalid polygon wkt")
        raw_points = [item.strip() for item in match.group(1).split(",") if item.strip()]
        points: list[tuple[float, float]] = []
        for raw in raw_points:
            parts = raw.split()
            if len(parts) != 2:
                raise ConflictError("invalid polygon point format")
            lon = float(parts[0])
            lat = float(parts[1])
            points.append((lon, lat))
        if len(points) < 3:
            raise ConflictError("polygon must include at least 3 points")
        return points

    def _point_in_polygon(self, lon: float, lat: float, polygon: list[tuple[float, float]]) -> bool:
        inside = False
        j = len(polygon) - 1
        for i, (xi, yi) in enumerate(polygon):
            xj, yj = polygon[j]
            intersects = ((yi > lat) != (yj > lat)) and (
                lon < (xj - xi) * (lat - yi) / ((yj - yi) if (yj - yi) != 0 else 1e-12) + xi
            )
            if intersects:
                inside = not inside
            j = i
        return inside

    def _extract_plan_points(self, plan_type: MissionPlanType, payload: dict[str, Any]) -> list[_Point]:
        points: list[_Point] = []
        if plan_type == MissionPlanType.POINT_TASK:
            point = payload.get("point")
            if isinstance(point, dict):
                lat = point.get("lat")
                lon = point.get("lon")
                alt_m = point.get("alt_m")
                if isinstance(lat, int | float) and isinstance(lon, int | float):
                    points.append(
                        _Point(
                            lat=float(lat),
                            lon=float(lon),
                            alt_m=float(alt_m) if isinstance(alt_m, int | float) else None,
                        )
                    )
            return points

        if plan_type == MissionPlanType.ROUTE_WAYPOINTS:
            waypoints = payload.get("waypoints")
            if isinstance(waypoints, list):
                for item in waypoints:
                    if not isinstance(item, dict):
                        continue
                    lat = item.get("lat")
                    lon = item.get("lon")
                    alt_m = item.get("alt_m")
                    if isinstance(lat, int | float) and isinstance(lon, int | float):
                        points.append(
                            _Point(
                                lat=float(lat),
                                lon=float(lon),
                                alt_m=float(alt_m) if isinstance(alt_m, int | float) else None,
                            )
                        )
            return points

        area_polygon = payload.get("area_polygon")
        if isinstance(area_polygon, list):
            for item in area_polygon:
                if not isinstance(item, dict):
                    continue
                lat = item.get("lat")
                lon = item.get("lon")
                if isinstance(lat, int | float) and isinstance(lon, int | float):
                    points.append(_Point(lat=float(lat), lon=float(lon), alt_m=None))
        return points

    @staticmethod
    def _layer_rank(layer: AirspacePolicyLayer) -> int:
        if layer == AirspacePolicyLayer.ORG_UNIT:
            return 3
        if layer == AirspacePolicyLayer.TENANT:
            return 2
        return 1

    def _active_zones(
        self,
        session: Session,
        tenant_id: str,
        area_code: str | None,
        org_unit_id: str | None,
    ) -> list[AirspaceZone]:
        statement = (
            select(AirspaceZone)
            .where(AirspaceZone.tenant_id == tenant_id)
            .where(AirspaceZone.is_active == true())
        )
        zones = list(session.exec(statement).all())
        filtered: list[AirspaceZone] = []
        for zone in zones:
            if area_code is not None and zone.area_code not in {None, area_code}:
                continue
            if zone.policy_layer == AirspacePolicyLayer.ORG_UNIT and (
                org_unit_id is None or zone.org_unit_id != org_unit_id
            ):
                continue
            filtered.append(zone)
        return filtered

    def _record_decision(
        self,
        session: Session,
        *,
        tenant_id: str,
        source: str,
        entity_type: str,
        entity_id: str,
        decision: ComplianceDecision,
        reason_code: str | None,
        actor_id: str | None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        row = ComplianceDecisionRecord(
            tenant_id=tenant_id,
            source=source,
            entity_type=entity_type,
            entity_id=entity_id,
            decision=decision,
            reason_code=reason_code,
            actor_id=actor_id,
            detail=detail or {},
        )
        session.add(row)

    def create_approval(
        self,
        tenant_id: str,
        actor_id: str,
        payload: ApprovalRecordCreate,
    ) -> ApprovalRecord:
        with self._session() as session:
            row = ApprovalRecord(
                tenant_id=tenant_id,
                entity_type=payload.entity_type,
                entity_id=payload.entity_id,
                status=payload.status,
                approved_by=actor_id,
            )
            session.add(row)
            try:
                session.commit()
            except IntegrityError as exc:
                session.rollback()
                raise ConflictError("approval record create conflict") from exc
            session.refresh(row)
            return row

    def list_approvals(
        self,
        tenant_id: str,
        *,
        entity_type: str | None = None,
        entity_id: str | None = None,
    ) -> list[ApprovalRecord]:
        with self._session() as session:
            statement = select(ApprovalRecord).where(ApprovalRecord.tenant_id == tenant_id)
            if entity_type is not None:
                statement = statement.where(ApprovalRecord.entity_type == entity_type)
            if entity_id is not None:
                statement = statement.where(ApprovalRecord.entity_id == entity_id)
            return list(session.exec(statement).all())

    def export_audit(self, tenant_id: str) -> str:
        rows = self.list_approvals(tenant_id)
        export_dir = Path("tmp")
        export_dir.mkdir(parents=True, exist_ok=True)
        export_path = export_dir / f"audit_export_{tenant_id}_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.json"
        payload = [
            {
                "id": row.id,
                "tenant_id": row.tenant_id,
                "entity_type": row.entity_type,
                "entity_id": row.entity_id,
                "status": row.status,
                "approved_by": row.approved_by,
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ]
        export_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
        return str(export_path)

    def _get_scoped_approval_flow_template(
        self,
        session: Session,
        tenant_id: str,
        template_id: str,
    ) -> ComplianceApprovalFlowTemplate:
        row = session.exec(
            select(ComplianceApprovalFlowTemplate)
            .where(ComplianceApprovalFlowTemplate.tenant_id == tenant_id)
            .where(ComplianceApprovalFlowTemplate.id == template_id)
        ).first()
        if row is None:
            raise NotFoundError("approval flow template not found")
        return row

    def _get_scoped_approval_flow_instance(
        self,
        session: Session,
        tenant_id: str,
        instance_id: str,
    ) -> ComplianceApprovalFlowInstance:
        row = session.exec(
            select(ComplianceApprovalFlowInstance)
            .where(ComplianceApprovalFlowInstance.tenant_id == tenant_id)
            .where(ComplianceApprovalFlowInstance.id == instance_id)
        ).first()
        if row is None:
            raise NotFoundError("approval flow instance not found")
        return row

    def create_approval_flow_template(
        self,
        tenant_id: str,
        actor_id: str,
        payload: ComplianceApprovalFlowTemplateCreate,
    ) -> ComplianceApprovalFlowTemplate:
        with self._session() as session:
            row = ComplianceApprovalFlowTemplate(
                tenant_id=tenant_id,
                name=payload.name,
                entity_type=payload.entity_type,
                steps=payload.steps,
                is_active=payload.is_active,
                created_by=actor_id,
            )
            session.add(row)
            try:
                session.commit()
            except IntegrityError as exc:
                session.rollback()
                raise ConflictError("approval flow template create conflict") from exc
            session.refresh(row)
            return row

    def list_approval_flow_templates(
        self,
        tenant_id: str,
        *,
        entity_type: str | None = None,
        is_active: bool | None = None,
    ) -> list[ComplianceApprovalFlowTemplate]:
        with self._session() as session:
            statement = select(ComplianceApprovalFlowTemplate).where(ComplianceApprovalFlowTemplate.tenant_id == tenant_id)
            if entity_type is not None:
                statement = statement.where(ComplianceApprovalFlowTemplate.entity_type == entity_type)
            if is_active is not None:
                statement = statement.where(ComplianceApprovalFlowTemplate.is_active == is_active)
            return list(session.exec(statement).all())

    def create_approval_flow_instance(
        self,
        tenant_id: str,
        actor_id: str,
        payload: ComplianceApprovalFlowInstanceCreate,
    ) -> ComplianceApprovalFlowInstance:
        with self._session() as session:
            template = self._get_scoped_approval_flow_template(session, tenant_id, payload.template_id)
            if not template.is_active:
                raise ConflictError("approval flow template is inactive")
            if template.entity_type != payload.entity_type:
                raise ConflictError("approval flow template entity_type mismatch")
            if payload.entity_type == "MISSION":
                _ = self._get_scoped_mission(session, tenant_id, payload.entity_id)

            existing_pending = session.exec(
                select(ComplianceApprovalFlowInstance)
                .where(ComplianceApprovalFlowInstance.tenant_id == tenant_id)
                .where(ComplianceApprovalFlowInstance.entity_type == payload.entity_type)
                .where(ComplianceApprovalFlowInstance.entity_id == payload.entity_id)
                .where(ComplianceApprovalFlowInstance.status == ApprovalFlowInstanceStatus.PENDING)
            ).first()
            if existing_pending is not None:
                raise ConflictError("approval flow instance already pending for this entity")

            row = ComplianceApprovalFlowInstance(
                tenant_id=tenant_id,
                template_id=template.id,
                entity_type=payload.entity_type,
                entity_id=payload.entity_id,
                status=ApprovalFlowInstanceStatus.PENDING,
                current_step_index=0,
                steps_snapshot=template.steps,
                action_history=[],
                created_by=actor_id,
            )
            session.add(row)
            try:
                session.commit()
            except IntegrityError as exc:
                session.rollback()
                raise ConflictError("approval flow instance create conflict") from exc
            session.refresh(row)
            return row

    def get_approval_flow_instance(
        self,
        tenant_id: str,
        instance_id: str,
    ) -> ComplianceApprovalFlowInstance:
        with self._session() as session:
            return self._get_scoped_approval_flow_instance(session, tenant_id, instance_id)

    def act_approval_flow_instance(
        self,
        tenant_id: str,
        instance_id: str,
        actor_id: str,
        payload: ComplianceApprovalFlowInstanceActionRequest,
    ) -> ComplianceApprovalFlowInstance:
        with self._session() as session:
            row = self._get_scoped_approval_flow_instance(session, tenant_id, instance_id)
            steps = [item for item in row.steps_snapshot if isinstance(item, dict)]
            if not steps:
                raise ConflictError("approval flow instance has empty steps")
            if payload.action != ApprovalFlowAction.ROLLBACK and row.status != ApprovalFlowInstanceStatus.PENDING:
                raise ConflictError("approval flow instance is already completed")

            now = datetime.now(UTC)
            history = [item for item in row.action_history if isinstance(item, dict)]
            step_index = max(0, min(row.current_step_index, len(steps) - 1))
            step = steps[step_index]
            allowed_reviewers = step.get("reviewer_user_ids")
            if (
                payload.action in {ApprovalFlowAction.APPROVE, ApprovalFlowAction.REJECT}
                and isinstance(allowed_reviewers, list)
                and allowed_reviewers
                and actor_id not in {str(item) for item in allowed_reviewers}
            ):
                raise ConflictError("actor is not allowed for current approval step")

            history.append(
                {
                    "action": payload.action.value,
                    "step_index": step_index,
                    "actor_id": actor_id,
                    "note": payload.note,
                    "ts": now.isoformat(),
                }
            )

            if payload.action == ApprovalFlowAction.ROLLBACK:
                if row.status != ApprovalFlowInstanceStatus.PENDING:
                    raise ConflictError("cannot rollback a completed approval flow instance")
                if row.current_step_index <= 0:
                    raise ConflictError("approval flow instance already at first step")
                row.current_step_index = row.current_step_index - 1
            elif payload.action == ApprovalFlowAction.APPROVE:
                if row.current_step_index >= len(steps) - 1:
                    row.status = ApprovalFlowInstanceStatus.APPROVED
                    row.completed_at = now
                    if row.entity_type == "MISSION":
                        mission = self._get_scoped_mission(session, tenant_id, row.entity_id)
                        if not can_transition(mission.state, MissionState.APPROVED):
                            raise ConflictError(
                                f"illegal mission transition in approval flow: {mission.state} -> {MissionState.APPROVED}"
                            )
                        mission.state = MissionState.APPROVED
                        mission.updated_at = now
                        session.add(mission)
                        session.add(
                            ApprovalRecord(
                                tenant_id=tenant_id,
                                entity_type="MISSION",
                                entity_id=mission.id,
                                status=ApprovalFlowInstanceStatus.APPROVED.value,
                                approved_by=actor_id,
                            )
                        )
                    self._record_decision(
                        session,
                        tenant_id=tenant_id,
                        source="approval_flow",
                        entity_type=row.entity_type,
                        entity_id=row.entity_id,
                        decision=ComplianceDecision.APPROVE,
                        reason_code=None,
                        actor_id=actor_id,
                        detail={"instance_id": row.id, "step_index": step_index},
                    )
                else:
                    row.current_step_index = row.current_step_index + 1
            else:
                row.status = ApprovalFlowInstanceStatus.REJECTED
                row.completed_at = now
                if row.entity_type == "MISSION":
                    mission = self._get_scoped_mission(session, tenant_id, row.entity_id)
                    if not can_transition(mission.state, MissionState.REJECTED):
                        raise ConflictError(
                            f"illegal mission transition in approval flow: {mission.state} -> {MissionState.REJECTED}"
                        )
                    mission.state = MissionState.REJECTED
                    mission.updated_at = now
                    session.add(mission)
                    session.add(
                        ApprovalRecord(
                            tenant_id=tenant_id,
                            entity_type="MISSION",
                            entity_id=mission.id,
                            status=ApprovalFlowInstanceStatus.REJECTED.value,
                            approved_by=actor_id,
                        )
                    )
                self._record_decision(
                    session,
                    tenant_id=tenant_id,
                    source="approval_flow",
                    entity_type=row.entity_type,
                    entity_id=row.entity_id,
                    decision=ComplianceDecision.REJECT,
                    reason_code=None,
                    actor_id=actor_id,
                    detail={"instance_id": row.id, "step_index": step_index},
                )

            row.action_history = history
            row.updated_at = now
            session.add(row)
            session.commit()
            session.refresh(row)
            return row

    def list_decision_records(
        self,
        tenant_id: str,
        *,
        source: str | None = None,
        entity_type: str | None = None,
        entity_id: str | None = None,
    ) -> list[ComplianceDecisionRecord]:
        with self._session() as session:
            statement = select(ComplianceDecisionRecord).where(ComplianceDecisionRecord.tenant_id == tenant_id)
            if source is not None:
                statement = statement.where(ComplianceDecisionRecord.source == source)
            if entity_type is not None:
                statement = statement.where(ComplianceDecisionRecord.entity_type == entity_type)
            if entity_id is not None:
                statement = statement.where(ComplianceDecisionRecord.entity_id == entity_id)
            rows = list(session.exec(statement).all())
            return sorted(rows, key=lambda item: item.created_at)

    def export_decision_records(
        self,
        tenant_id: str,
        *,
        source: str | None = None,
        entity_type: str | None = None,
        entity_id: str | None = None,
    ) -> str:
        rows = self.list_decision_records(
            tenant_id,
            source=source,
            entity_type=entity_type,
            entity_id=entity_id,
        )
        export_dir = Path("tmp")
        export_dir.mkdir(parents=True, exist_ok=True)
        export_path = export_dir / f"compliance_decisions_{tenant_id}_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.json"
        payload = [
            {
                "id": row.id,
                "tenant_id": row.tenant_id,
                "source": row.source,
                "entity_type": row.entity_type,
                "entity_id": row.entity_id,
                "decision": row.decision.value,
                "reason_code": row.reason_code,
                "actor_id": row.actor_id,
                "detail": row.detail,
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ]
        export_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
        return str(export_path)

    def build_mission_compliance_snapshot(
        self,
        session: Session,
        tenant_id: str,
        mission_id: str,
    ) -> dict[str, Any]:
        mission = self._get_scoped_mission(session, tenant_id, mission_id)
        checklist = session.exec(
            select(MissionPreflightChecklist)
            .where(MissionPreflightChecklist.tenant_id == tenant_id)
            .where(MissionPreflightChecklist.mission_id == mission_id)
        ).first()
        flow_instance = session.exec(
            select(ComplianceApprovalFlowInstance)
            .where(ComplianceApprovalFlowInstance.tenant_id == tenant_id)
            .where(ComplianceApprovalFlowInstance.entity_type == "MISSION")
            .where(ComplianceApprovalFlowInstance.entity_id == mission_id)
        ).first()
        mission_decisions = list(
            session.exec(
                select(ComplianceDecisionRecord)
                .where(ComplianceDecisionRecord.tenant_id == tenant_id)
                .where(ComplianceDecisionRecord.entity_type == "MISSION")
                .where(ComplianceDecisionRecord.entity_id == mission_id)
            ).all()
        )
        latest_decision = None
        if mission_decisions:
            latest_decision = sorted(mission_decisions, key=lambda item: item.created_at)[-1]
        return {
            "mission_id": mission.id,
            "mission_state": mission.state.value,
            "preflight": {
                "status": checklist.status.value if checklist is not None else None,
                "completed_at": checklist.completed_at.isoformat() if checklist and checklist.completed_at else None,
            },
            "approval_flow": (
                {
                    "instance_id": flow_instance.id,
                    "status": flow_instance.status.value,
                    "current_step_index": flow_instance.current_step_index,
                }
                if flow_instance is not None
                else None
            ),
            "latest_decision": (
                {
                    "id": latest_decision.id,
                    "source": latest_decision.source,
                    "decision": latest_decision.decision.value,
                    "reason_code": latest_decision.reason_code,
                    "created_at": latest_decision.created_at.isoformat(),
                }
                if latest_decision is not None
                else None
            ),
        }

    def _reason_code_for_zone_type(
        self,
        zone_type: AirspaceZoneType,
        *,
        for_command: bool = False,
    ) -> ComplianceReasonCode:
        if zone_type == AirspaceZoneType.NO_FLY:
            return (
                ComplianceReasonCode.COMMAND_GEOFENCE_BLOCKED
                if for_command
                else ComplianceReasonCode.AIRSPACE_NO_FLY
            )
        if zone_type == AirspaceZoneType.ALT_LIMIT:
            return (
                ComplianceReasonCode.COMMAND_ALTITUDE_BLOCKED
                if for_command
                else ComplianceReasonCode.AIRSPACE_ALT_LIMIT_EXCEEDED
            )
        return (
            ComplianceReasonCode.COMMAND_SENSITIVE_RESTRICTED
            if for_command
            else ComplianceReasonCode.AIRSPACE_SENSITIVE_RESTRICTED
        )

    def _build_zone_detail(self, zone: AirspaceZone) -> dict[str, Any]:
        return {
            "zone_id": zone.id,
            "zone_name": zone.name,
            "zone_type": zone.zone_type.value,
            "policy_layer": zone.policy_layer.value,
            "policy_effect": zone.policy_effect.value,
            "org_unit_id": zone.org_unit_id,
        }

    def _deny_violation_for_zone(
        self,
        *,
        zone: AirspaceZone,
        point: _Point,
        sensitive_override: bool,
        emergency_fastlane: bool,
        for_command: bool = False,
        command_type: CommandType | None = None,
    ) -> ComplianceViolationError | None:
        if zone.policy_effect != AirspacePolicyEffect.DENY:
            return None

        if zone.zone_type == AirspaceZoneType.NO_FLY:
            detail = self._build_zone_detail(zone)
            if command_type is not None:
                detail["command_type"] = command_type.value
            return ComplianceViolationError(
                self._reason_code_for_zone_type(zone.zone_type, for_command=for_command),
                "point enters no-fly zone" if not for_command else "command target enters no-fly zone",
                detail=detail,
            )

        if zone.zone_type == AirspaceZoneType.ALT_LIMIT:
            if zone.max_alt_m is None or point.alt_m is None or point.alt_m <= zone.max_alt_m:
                return None
            detail = self._build_zone_detail(zone)
            detail["max_alt_m"] = zone.max_alt_m
            detail["point_alt_m"] = point.alt_m
            if for_command:
                detail["target_alt_m"] = point.alt_m
            return ComplianceViolationError(
                self._reason_code_for_zone_type(zone.zone_type, for_command=for_command),
                "point altitude exceeds zone limit"
                if not for_command
                else "command altitude exceeds zone limit",
                detail=detail,
            )

        if sensitive_override or emergency_fastlane:
            return None
        detail = self._build_zone_detail(zone)
        if command_type is not None:
            detail["command_type"] = command_type.value
        return ComplianceViolationError(
            self._reason_code_for_zone_type(zone.zone_type, for_command=for_command),
            "point enters sensitive zone without override"
            if not for_command
            else "command target enters sensitive zone without override",
            detail=detail,
        )

    def _check_points_against_zones(
        self,
        *,
        points: list[_Point],
        zones: list[AirspaceZone],
        constraints: dict[str, Any],
        for_command: bool = False,
        command_type: CommandType | None = None,
    ) -> None:
        sensitive_override = bool(constraints.get("sensitive_override", False))
        emergency_fastlane = bool(constraints.get("emergency_fastlane", False))

        for point in points:
            layers = sorted(
                {zone.policy_layer for zone in zones},
                key=self._layer_rank,
                reverse=True,
            )
            for layer in layers:
                layer_hits: list[AirspaceZone] = []
                for zone in zones:
                    if zone.policy_layer != layer:
                        continue
                    polygon = self._parse_polygon_wkt(zone.geom_wkt)
                    if self._point_in_polygon(point.lon, point.lat, polygon):
                        layer_hits.append(zone)
                if not layer_hits:
                    continue

                for zone in layer_hits:
                    violation = self._deny_violation_for_zone(
                        zone=zone,
                        point=point,
                        sensitive_override=sensitive_override,
                        emergency_fastlane=emergency_fastlane,
                        for_command=for_command,
                        command_type=command_type,
                    )
                    if violation is not None:
                        raise violation
                if any(item.policy_effect == AirspacePolicyEffect.ALLOW for item in layer_hits):
                    break

    def validate_mission_plan(
        self,
        *,
        session: Session,
        tenant_id: str,
        plan_type: MissionPlanType,
        payload: dict[str, Any],
        constraints: dict[str, Any],
        area_code: str | None,
        org_unit_id: str | None = None,
        mission_id: str | None = None,
        actor_id: str | None = None,
    ) -> None:
        points = self._extract_plan_points(plan_type, payload)
        if not points:
            return
        zones = self._active_zones(session, tenant_id, area_code, org_unit_id)
        if not zones:
            return
        try:
            self._check_points_against_zones(points=points, zones=zones, constraints=constraints)
        except ComplianceViolationError as exc:
            self._record_decision(
                session,
                tenant_id=tenant_id,
                source="mission_plan",
                entity_type="MISSION",
                entity_id=mission_id or "DRAFT",
                decision=ComplianceDecision.DENY,
                reason_code=exc.reason_code.value,
                actor_id=actor_id,
                detail=exc.detail,
            )
            raise
        self._record_decision(
            session,
            tenant_id=tenant_id,
            source="mission_plan",
            entity_type="MISSION",
            entity_id=mission_id or "DRAFT",
            decision=ComplianceDecision.ALLOW,
            reason_code=None,
            actor_id=actor_id,
            detail={"area_code": area_code, "org_unit_id": org_unit_id},
        )

    def create_airspace_zone(self, tenant_id: str, actor_id: str, payload: AirspaceZoneCreate) -> AirspaceZone:
        with self._session() as session:
            if payload.policy_layer == AirspacePolicyLayer.ORG_UNIT:
                if payload.org_unit_id is None:
                    raise ConflictError("ORG_UNIT policy layer requires org_unit_id")
                _ = self._get_scoped_org_unit(session, tenant_id, payload.org_unit_id)
            elif payload.org_unit_id is not None:
                raise ConflictError("org_unit_id is only allowed for ORG_UNIT policy layer")
            row = AirspaceZone(
                tenant_id=tenant_id,
                name=payload.name,
                zone_type=payload.zone_type,
                policy_layer=payload.policy_layer,
                policy_effect=payload.policy_effect,
                org_unit_id=payload.org_unit_id,
                area_code=payload.area_code,
                geom_wkt=payload.geom_wkt,
                max_alt_m=payload.max_alt_m,
                is_active=payload.is_active,
                detail=payload.detail,
                created_by=actor_id,
            )
            _ = self._parse_polygon_wkt(payload.geom_wkt)
            if payload.zone_type == AirspaceZoneType.ALT_LIMIT and payload.max_alt_m is None:
                raise ConflictError("ALT_LIMIT zone requires max_alt_m")
            session.add(row)
            try:
                session.commit()
            except IntegrityError as exc:
                session.rollback()
                raise ConflictError("airspace zone create conflict") from exc
            session.refresh(row)
            return row

    def list_airspace_zones(
        self,
        tenant_id: str,
        *,
        zone_type: AirspaceZoneType | None = None,
        policy_layer: AirspacePolicyLayer | None = None,
        org_unit_id: str | None = None,
        is_active: bool | None = None,
    ) -> list[AirspaceZone]:
        with self._session() as session:
            statement = select(AirspaceZone).where(AirspaceZone.tenant_id == tenant_id)
            if zone_type is not None:
                statement = statement.where(AirspaceZone.zone_type == zone_type)
            if policy_layer is not None:
                statement = statement.where(AirspaceZone.policy_layer == policy_layer)
            if org_unit_id is not None:
                statement = statement.where(AirspaceZone.org_unit_id == org_unit_id)
            if is_active is not None:
                statement = statement.where(AirspaceZone.is_active == is_active)
            return list(session.exec(statement).all())

    def get_airspace_zone(self, tenant_id: str, zone_id: str) -> AirspaceZone:
        with self._session() as session:
            return self._get_scoped_zone(session, tenant_id, zone_id)

    def create_preflight_template(
        self,
        tenant_id: str,
        actor_id: str,
        payload: PreflightChecklistTemplateCreate,
    ) -> PreflightChecklistTemplate:
        with self._session() as session:
            row = PreflightChecklistTemplate(
                tenant_id=tenant_id,
                name=payload.name,
                description=payload.description,
                items=payload.items,
                template_version=payload.template_version,
                evidence_requirements=payload.evidence_requirements,
                require_approval_before_run=payload.require_approval_before_run,
                is_active=payload.is_active,
                created_by=actor_id,
            )
            session.add(row)
            try:
                session.commit()
            except IntegrityError as exc:
                session.rollback()
                raise ConflictError("preflight checklist template create conflict") from exc
            session.refresh(row)
            return row

    def list_preflight_templates(
        self,
        tenant_id: str,
        *,
        is_active: bool | None = None,
    ) -> list[PreflightChecklistTemplate]:
        with self._session() as session:
            statement = select(PreflightChecklistTemplate).where(PreflightChecklistTemplate.tenant_id == tenant_id)
            if is_active is not None:
                statement = statement.where(PreflightChecklistTemplate.is_active == is_active)
            return list(session.exec(statement).all())

    def init_mission_preflight_checklist(
        self,
        tenant_id: str,
        mission_id: str,
        actor_id: str,
        payload: MissionPreflightChecklistInitRequest,
    ) -> MissionPreflightChecklist:
        with self._session() as session:
            mission = self._get_scoped_mission(session, tenant_id, mission_id)
            template: PreflightChecklistTemplate | None = None
            if payload.template_id is not None:
                template = self._get_scoped_template(session, tenant_id, payload.template_id)
                if not template.is_active:
                    raise ConflictError("preflight checklist template is inactive")

            required_items = payload.required_items if payload.required_items else (template.items if template else [])
            if not required_items:
                raise ConflictError("preflight checklist required_items cannot be empty")

            existing = session.exec(
                select(MissionPreflightChecklist)
                .where(MissionPreflightChecklist.tenant_id == tenant_id)
                .where(MissionPreflightChecklist.mission_id == mission_id)
            ).first()
            if existing is None:
                existing = MissionPreflightChecklist(
                    tenant_id=tenant_id,
                    mission_id=mission.id,
                    template_id=template.id if template is not None else None,
                    status=PreflightChecklistStatus.PENDING,
                    required_items=required_items,
                    completed_items=[],
                    evidence={},
                    updated_by=actor_id,
                )
            else:
                existing.template_id = template.id if template is not None else None
                existing.required_items = required_items
                existing.completed_items = []
                existing.status = PreflightChecklistStatus.PENDING
                existing.completed_at = None
                existing.updated_at = datetime.now(UTC)
                existing.updated_by = actor_id
            session.add(existing)
            session.commit()
            session.refresh(existing)
            return existing

    def get_mission_preflight_checklist(self, tenant_id: str, mission_id: str) -> MissionPreflightChecklist:
        with self._session() as session:
            _ = self._get_scoped_mission(session, tenant_id, mission_id)
            return self._get_scoped_preflight_by_mission(session, tenant_id, mission_id)

    def check_mission_preflight_item(
        self,
        tenant_id: str,
        mission_id: str,
        actor_id: str,
        payload: MissionPreflightChecklistItemCheckRequest,
    ) -> MissionPreflightChecklist:
        with self._session() as session:
            _ = self._get_scoped_mission(session, tenant_id, mission_id)
            checklist = self._get_scoped_preflight_by_mission(session, tenant_id, mission_id)
            template: PreflightChecklistTemplate | None = None
            if checklist.template_id is not None:
                template = self._get_scoped_template(session, tenant_id, checklist.template_id)
            evidence_required = bool((template.evidence_requirements if template is not None else {}).get("required", False))

            required_codes = {
                str(item.get("code"))
                for item in checklist.required_items
                if isinstance(item, dict) and isinstance(item.get("code"), str)
            }
            if payload.item_code not in required_codes:
                raise ConflictError("item code not in required_items")

            completed = [
                item
                for item in checklist.completed_items
                if isinstance(item, dict) and item.get("item_code") != payload.item_code
            ]
            if payload.checked:
                if evidence_required and not payload.evidence:
                    raise ConflictError("evidence is required for this checklist template")
                completed.append(
                    {
                        "item_code": payload.item_code,
                        "checked": True,
                        "note": payload.note,
                        "checked_by": actor_id,
                        "checked_at": datetime.now(UTC).isoformat(),
                    }
                )
                evidence = dict(checklist.evidence)
                evidence[payload.item_code] = payload.evidence
                checklist.evidence = evidence

            checklist.completed_items = completed
            completed_codes = {
                str(item.get("item_code"))
                for item in completed
                if isinstance(item, dict) and item.get("checked") is True
            }
            if required_codes.issubset(completed_codes):
                checklist.status = PreflightChecklistStatus.COMPLETED
                checklist.completed_at = datetime.now(UTC)
            else:
                checklist.status = PreflightChecklistStatus.IN_PROGRESS
            checklist.updated_by = actor_id
            checklist.updated_at = datetime.now(UTC)
            session.add(checklist)
            session.commit()
            session.refresh(checklist)
            return checklist

    def enforce_before_mission_run(
        self,
        *,
        session: Session,
        tenant_id: str,
        mission: Mission,
    ) -> dict[str, Any]:
        if mission.constraints.get("emergency_fastlane", False):
            self._record_decision(
                session,
                tenant_id=tenant_id,
                source="preflight_gate",
                entity_type="MISSION",
                entity_id=mission.id,
                decision=ComplianceDecision.ALLOW,
                reason_code=ComplianceReasonCode.PREFLIGHT_CHECKLIST_REQUIRED.value,
                actor_id=None,
                detail={"waived": True, "reason": "emergency_fastlane"},
            )
            return {
                "passed": True,
                "waived": True,
                "reason_code": ComplianceReasonCode.PREFLIGHT_CHECKLIST_REQUIRED,
                "message": "preflight checklist waived by emergency fastlane",
            }

        flow_instance = session.exec(
            select(ComplianceApprovalFlowInstance)
            .where(ComplianceApprovalFlowInstance.tenant_id == tenant_id)
            .where(ComplianceApprovalFlowInstance.entity_type == "MISSION")
            .where(ComplianceApprovalFlowInstance.entity_id == mission.id)
        ).first()
        if flow_instance is not None and flow_instance.status == ApprovalFlowInstanceStatus.PENDING:
            detail = {"mission_id": mission.id, "flow_instance_id": flow_instance.id}
            self._record_decision(
                session,
                tenant_id=tenant_id,
                source="preflight_gate",
                entity_type="MISSION",
                entity_id=mission.id,
                decision=ComplianceDecision.DENY,
                reason_code=ComplianceReasonCode.APPROVAL_FLOW_PENDING.value,
                actor_id=None,
                detail=detail,
            )
            raise ComplianceViolationError(
                ComplianceReasonCode.APPROVAL_FLOW_PENDING,
                "approval flow is still pending",
                detail=detail,
            )

        checklist = session.exec(
            select(MissionPreflightChecklist)
            .where(MissionPreflightChecklist.tenant_id == tenant_id)
            .where(MissionPreflightChecklist.mission_id == mission.id)
        ).first()
        if checklist is None:
            detail = {"mission_id": mission.id}
            self._record_decision(
                session,
                tenant_id=tenant_id,
                source="preflight_gate",
                entity_type="MISSION",
                entity_id=mission.id,
                decision=ComplianceDecision.DENY,
                reason_code=ComplianceReasonCode.PREFLIGHT_CHECKLIST_REQUIRED.value,
                actor_id=None,
                detail=detail,
            )
            raise ComplianceViolationError(
                ComplianceReasonCode.PREFLIGHT_CHECKLIST_REQUIRED,
                "preflight checklist required before mission run",
                detail=detail,
            )
        if checklist.status != PreflightChecklistStatus.COMPLETED:
            incomplete_detail: dict[str, Any] = {
                "mission_id": mission.id,
                "status": checklist.status,
                "required_count": len(checklist.required_items),
                "completed_count": len(checklist.completed_items),
            }
            self._record_decision(
                session,
                tenant_id=tenant_id,
                source="preflight_gate",
                entity_type="MISSION",
                entity_id=mission.id,
                decision=ComplianceDecision.DENY,
                reason_code=ComplianceReasonCode.PREFLIGHT_CHECKLIST_INCOMPLETE.value,
                actor_id=None,
                detail=incomplete_detail,
            )
            raise ComplianceViolationError(
                ComplianceReasonCode.PREFLIGHT_CHECKLIST_INCOMPLETE,
                "preflight checklist is not completed",
                detail=incomplete_detail,
            )
        self._record_decision(
            session,
            tenant_id=tenant_id,
            source="preflight_gate",
            entity_type="MISSION",
            entity_id=mission.id,
            decision=ComplianceDecision.ALLOW,
            reason_code=None,
            actor_id=None,
            detail={"waived": False},
        )
        return {"passed": True, "waived": False}

    def validate_command_precheck(
        self,
        *,
        session: Session,
        tenant_id: str,
        drone_id: str,
        command_type: CommandType,
        params: dict[str, Any],
        actor_id: str | None = None,
    ) -> dict[str, Any]:
        if command_type not in {CommandType.GOTO, CommandType.START_MISSION}:
            return {"passed": True}

        if command_type == CommandType.START_MISSION:
            mission_id = params.get("mission_id")
            if isinstance(mission_id, str) and mission_id:
                mission = self._get_scoped_mission(session, tenant_id, mission_id)
                flow_instance = session.exec(
                    select(ComplianceApprovalFlowInstance)
                    .where(ComplianceApprovalFlowInstance.tenant_id == tenant_id)
                    .where(ComplianceApprovalFlowInstance.entity_type == "MISSION")
                    .where(ComplianceApprovalFlowInstance.entity_id == mission.id)
                ).first()
                if flow_instance is not None and flow_instance.status == ApprovalFlowInstanceStatus.PENDING:
                    detail = {"mission_id": mission.id, "flow_instance_id": flow_instance.id}
                    self._record_decision(
                        session,
                        tenant_id=tenant_id,
                        source="command_precheck",
                        entity_type="COMMAND",
                        entity_id=f"START_MISSION:{mission.id}",
                        decision=ComplianceDecision.DENY,
                        reason_code=ComplianceReasonCode.APPROVAL_FLOW_PENDING.value,
                        actor_id=actor_id,
                        detail=detail,
                    )
                    raise ComplianceViolationError(
                        ComplianceReasonCode.APPROVAL_FLOW_PENDING,
                        "approval flow is still pending",
                        detail=detail,
                    )
                if mission.state != MissionState.APPROVED:
                    detail = {"mission_id": mission.id, "mission_state": mission.state}
                    self._record_decision(
                        session,
                        tenant_id=tenant_id,
                        source="command_precheck",
                        entity_type="COMMAND",
                        entity_id=f"START_MISSION:{mission.id}",
                        decision=ComplianceDecision.DENY,
                        reason_code=ComplianceReasonCode.PREFLIGHT_CHECKLIST_INCOMPLETE.value,
                        actor_id=actor_id,
                        detail=detail,
                    )
                    raise ComplianceViolationError(
                        ComplianceReasonCode.PREFLIGHT_CHECKLIST_INCOMPLETE,
                        "mission must be APPROVED before START_MISSION",
                        detail=detail,
                    )
                _ = self.enforce_before_mission_run(
                    session=session,
                    tenant_id=tenant_id,
                    mission=mission,
                )
                self._record_decision(
                    session,
                    tenant_id=tenant_id,
                    source="command_precheck",
                    entity_type="COMMAND",
                    entity_id=f"START_MISSION:{mission.id}",
                    decision=ComplianceDecision.ALLOW,
                    reason_code=None,
                    actor_id=actor_id,
                    detail={"mission_id": mission.id, "drone_id": drone_id},
                )
                return {
                    "passed": True,
                    "mission_id": mission.id,
                    "drone_id": drone_id,
                }
            return {"passed": True}

        lat = params.get("lat")
        lon = params.get("lon")
        alt_m = params.get("alt_m")
        if not isinstance(lat, int | float) or not isinstance(lon, int | float):
            return {"passed": True}

        point = _Point(
            lat=float(lat),
            lon=float(lon),
            alt_m=float(alt_m) if isinstance(alt_m, int | float) else None,
        )
        zones = self._active_zones(
            session,
            tenant_id,
            params.get("area_code") if isinstance(params.get("area_code"), str) else None,
            params.get("org_unit_id") if isinstance(params.get("org_unit_id"), str) else None,
        )
        if not zones:
            return {"passed": True}

        try:
            self._check_points_against_zones(
                points=[point],
                zones=zones,
                constraints=params,
                for_command=True,
                command_type=command_type,
            )
        except ComplianceViolationError as exc:
            self._record_decision(
                session,
                tenant_id=tenant_id,
                source="command_precheck",
                entity_type="COMMAND",
                entity_id=f"{command_type.value}:{drone_id}",
                decision=ComplianceDecision.DENY,
                reason_code=exc.reason_code.value,
                actor_id=actor_id,
                detail=exc.detail,
            )
            raise
        self._record_decision(
            session,
            tenant_id=tenant_id,
            source="command_precheck",
            entity_type="COMMAND",
            entity_id=f"{command_type.value}:{drone_id}",
            decision=ComplianceDecision.ALLOW,
            reason_code=None,
            actor_id=actor_id,
            detail={"drone_id": drone_id, "command_type": command_type.value},
        )
        return {"passed": True}
