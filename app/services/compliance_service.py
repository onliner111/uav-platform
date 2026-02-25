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
    AirspaceZone,
    AirspaceZoneCreate,
    AirspaceZoneType,
    ApprovalRecord,
    ApprovalRecordCreate,
    CommandType,
    ComplianceReasonCode,
    Mission,
    MissionPlanType,
    MissionPreflightChecklist,
    MissionPreflightChecklistInitRequest,
    MissionPreflightChecklistItemCheckRequest,
    PreflightChecklistStatus,
    PreflightChecklistTemplate,
    PreflightChecklistTemplateCreate,
)
from app.domain.state_machine import MissionState
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

    def _active_zones(self, session: Session, tenant_id: str, area_code: str | None) -> list[AirspaceZone]:
        statement = (
            select(AirspaceZone)
            .where(AirspaceZone.tenant_id == tenant_id)
            .where(AirspaceZone.is_active == true())
        )
        zones = list(session.exec(statement).all())
        if area_code is None:
            return zones
        return [item for item in zones if item.area_code in {None, area_code}]

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

    def _check_points_against_zones(
        self,
        *,
        points: list[_Point],
        zones: list[AirspaceZone],
        constraints: dict[str, Any],
    ) -> None:
        sensitive_override = bool(constraints.get("sensitive_override", False))
        emergency_fastlane = bool(constraints.get("emergency_fastlane", False))

        for point in points:
            for zone in zones:
                polygon = self._parse_polygon_wkt(zone.geom_wkt)
                if not self._point_in_polygon(point.lon, point.lat, polygon):
                    continue
                if zone.zone_type == AirspaceZoneType.NO_FLY:
                    raise ComplianceViolationError(
                        ComplianceReasonCode.AIRSPACE_NO_FLY,
                        "point enters no-fly zone",
                        detail={"zone_id": zone.id, "zone_name": zone.name},
                    )
                if zone.zone_type == AirspaceZoneType.ALT_LIMIT:
                    if zone.max_alt_m is not None and point.alt_m is not None and point.alt_m > zone.max_alt_m:
                        raise ComplianceViolationError(
                            ComplianceReasonCode.AIRSPACE_ALT_LIMIT_EXCEEDED,
                            "point altitude exceeds zone limit",
                            detail={
                                "zone_id": zone.id,
                                "zone_name": zone.name,
                                "max_alt_m": zone.max_alt_m,
                                "point_alt_m": point.alt_m,
                            },
                        )
                    continue
                if zone.zone_type == AirspaceZoneType.SENSITIVE and not (sensitive_override or emergency_fastlane):
                    raise ComplianceViolationError(
                        ComplianceReasonCode.AIRSPACE_SENSITIVE_RESTRICTED,
                        "point enters sensitive zone without override",
                        detail={"zone_id": zone.id, "zone_name": zone.name},
                    )

    def validate_mission_plan(
        self,
        *,
        session: Session,
        tenant_id: str,
        plan_type: MissionPlanType,
        payload: dict[str, Any],
        constraints: dict[str, Any],
        area_code: str | None,
    ) -> None:
        points = self._extract_plan_points(plan_type, payload)
        if not points:
            return
        zones = self._active_zones(session, tenant_id, area_code)
        if not zones:
            return
        self._check_points_against_zones(points=points, zones=zones, constraints=constraints)

    def create_airspace_zone(self, tenant_id: str, actor_id: str, payload: AirspaceZoneCreate) -> AirspaceZone:
        with self._session() as session:
            row = AirspaceZone(
                tenant_id=tenant_id,
                name=payload.name,
                zone_type=payload.zone_type,
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
        is_active: bool | None = None,
    ) -> list[AirspaceZone]:
        with self._session() as session:
            statement = select(AirspaceZone).where(AirspaceZone.tenant_id == tenant_id)
            if zone_type is not None:
                statement = statement.where(AirspaceZone.zone_type == zone_type)
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
                completed.append(
                    {
                        "item_code": payload.item_code,
                        "checked": True,
                        "note": payload.note,
                        "checked_by": actor_id,
                        "checked_at": datetime.now(UTC).isoformat(),
                    }
                )

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
            return {
                "passed": True,
                "waived": True,
                "reason_code": ComplianceReasonCode.PREFLIGHT_CHECKLIST_REQUIRED,
                "message": "preflight checklist waived by emergency fastlane",
            }

        checklist = session.exec(
            select(MissionPreflightChecklist)
            .where(MissionPreflightChecklist.tenant_id == tenant_id)
            .where(MissionPreflightChecklist.mission_id == mission.id)
        ).first()
        if checklist is None:
            raise ComplianceViolationError(
                ComplianceReasonCode.PREFLIGHT_CHECKLIST_REQUIRED,
                "preflight checklist required before mission run",
                detail={"mission_id": mission.id},
            )
        if checklist.status != PreflightChecklistStatus.COMPLETED:
            raise ComplianceViolationError(
                ComplianceReasonCode.PREFLIGHT_CHECKLIST_INCOMPLETE,
                "preflight checklist is not completed",
                detail={
                    "mission_id": mission.id,
                    "status": checklist.status,
                    "required_count": len(checklist.required_items),
                    "completed_count": len(checklist.completed_items),
                },
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
    ) -> dict[str, Any]:
        if command_type not in {CommandType.GOTO, CommandType.START_MISSION}:
            return {"passed": True}

        if command_type == CommandType.START_MISSION:
            mission_id = params.get("mission_id")
            if isinstance(mission_id, str) and mission_id:
                mission = self._get_scoped_mission(session, tenant_id, mission_id)
                if mission.state != MissionState.APPROVED:
                    raise ComplianceViolationError(
                        ComplianceReasonCode.PREFLIGHT_CHECKLIST_INCOMPLETE,
                        "mission must be APPROVED before START_MISSION",
                        detail={"mission_id": mission.id, "mission_state": mission.state},
                    )
                _ = self.enforce_before_mission_run(
                    session=session,
                    tenant_id=tenant_id,
                    mission=mission,
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
        zones = self._active_zones(session, tenant_id, params.get("area_code") if isinstance(params.get("area_code"), str) else None)
        if not zones:
            return {"passed": True}

        sensitive_override = bool(params.get("sensitive_override", False))
        for zone in zones:
            polygon = self._parse_polygon_wkt(zone.geom_wkt)
            if not self._point_in_polygon(point.lon, point.lat, polygon):
                continue
            if zone.zone_type == AirspaceZoneType.NO_FLY:
                raise ComplianceViolationError(
                    ComplianceReasonCode.COMMAND_GEOFENCE_BLOCKED,
                    "command target enters no-fly zone",
                    detail={"zone_id": zone.id, "zone_name": zone.name, "command_type": command_type},
                )
            if zone.zone_type == AirspaceZoneType.ALT_LIMIT:
                if zone.max_alt_m is not None and point.alt_m is not None and point.alt_m > zone.max_alt_m:
                    raise ComplianceViolationError(
                        ComplianceReasonCode.COMMAND_ALTITUDE_BLOCKED,
                        "command altitude exceeds zone limit",
                        detail={
                            "zone_id": zone.id,
                            "zone_name": zone.name,
                            "max_alt_m": zone.max_alt_m,
                            "target_alt_m": point.alt_m,
                        },
                    )
                continue
            if zone.zone_type == AirspaceZoneType.SENSITIVE and not sensitive_override:
                raise ComplianceViolationError(
                    ComplianceReasonCode.COMMAND_SENSITIVE_RESTRICTED,
                    "command target enters sensitive zone without override",
                    detail={"zone_id": zone.id, "zone_name": zone.name, "command_type": command_type},
                )

        return {"passed": True}
