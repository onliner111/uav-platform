from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlmodel import Session, select

from app.domain.models import (
    AirspaceZone,
    AlertRecord,
    AlertStatus,
    Asset,
    Drone,
    EventRecord,
    Incident,
    InspectionTask,
    MapLayerItemRead,
    MapLayerName,
    MapLayerRead,
    MapOverviewRead,
    MapPointRead,
    MapTrackPointRead,
    MapTrackReplayRead,
    Mission,
    OutcomeCatalogRecord,
    TelemetryNormalized,
)
from app.infra.db import get_engine
from app.services.data_perimeter_service import DataPerimeterService

POINT_WKT_PATTERN = re.compile(
    r"^POINT\s*\(\s*([-+]?\d*\.?\d+)\s+([-+]?\d*\.?\d+)\s*\)$",
    re.IGNORECASE,
)
POLYGON_COORD_PATTERN = re.compile(r"([-+]?\d*\.?\d+)\s+([-+]?\d*\.?\d+)")


class MapError(Exception):
    pass


class NotFoundError(MapError):
    pass


@dataclass(frozen=True)
class _TelemetryPoint:
    drone_id: str
    ts: datetime
    lat: float
    lon: float
    alt_m: float | None
    mode: str | None


class MapService:
    def __init__(self) -> None:
        self._data_perimeter = DataPerimeterService()

    def _session(self) -> Session:
        return Session(get_engine(), expire_on_commit=False)

    def _ensure_scoped_drone(self, session: Session, tenant_id: str, drone_id: str) -> None:
        drone = session.exec(
            select(Drone).where(Drone.tenant_id == tenant_id).where(Drone.id == drone_id)
        ).first()
        if drone is None:
            raise NotFoundError("drone not found")

    def _parse_wkt_focus_point(self, value: str | None) -> MapPointRead | None:
        if value is None:
            return None
        text = value.strip()
        match = POINT_WKT_PATTERN.match(text)
        if match is None:
            if not text.upper().startswith("POLYGON"):
                return None
            coords = [(float(lon), float(lat)) for lon, lat in POLYGON_COORD_PATTERN.findall(text)]
            if not coords:
                return None
            lon = sum(item[0] for item in coords) / len(coords)
            lat = sum(item[1] for item in coords) / len(coords)
        else:
            lon = float(match.group(1))
            lat = float(match.group(2))
        return MapPointRead(lat=lat, lon=lon)

    def _payload_to_telemetry(self, payload: dict[str, Any], fallback_ts: datetime) -> _TelemetryPoint | None:
        try:
            normalized = TelemetryNormalized.model_validate(payload)
        except Exception:
            return None
        ts = normalized.ts if normalized.ts is not None else fallback_ts
        return _TelemetryPoint(
            drone_id=normalized.drone_id,
            ts=ts,
            lat=normalized.position.lat,
            lon=normalized.position.lon,
            alt_m=normalized.position.alt_m,
            mode=normalized.mode,
        )

    def _latest_telemetry_by_drone(self, session: Session, tenant_id: str) -> dict[str, _TelemetryPoint]:
        rows = list(
            session.exec(
                select(EventRecord)
                .where(EventRecord.tenant_id == tenant_id)
                .where(EventRecord.event_type == "telemetry.normalized")
            ).all()
        )
        latest: dict[str, _TelemetryPoint] = {}
        for row in rows:
            point = self._payload_to_telemetry(row.payload, row.ts)
            if point is None:
                continue
            existing = latest.get(point.drone_id)
            if existing is None or point.ts > existing.ts:
                latest[point.drone_id] = point
        return latest

    def resources_layer(self, tenant_id: str, *, limit: int = 100) -> MapLayerRead:
        with self._session() as session:
            telemetry = self._latest_telemetry_by_drone(session, tenant_id)
            drones = list(session.exec(select(Drone).where(Drone.tenant_id == tenant_id)).all())
            assets = list(session.exec(select(Asset).where(Asset.tenant_id == tenant_id)).all())

        items: list[MapLayerItemRead] = []
        for drone in drones:
            point = telemetry.get(drone.id)
            items.append(
                MapLayerItemRead(
                    id=drone.id,
                    category="drone",
                    label=drone.name,
                    status="ONLINE" if point is not None else "UNKNOWN",
                    point=(
                        MapPointRead(lat=point.lat, lon=point.lon, alt_m=point.alt_m, ts=point.ts)
                        if point is not None
                        else None
                    ),
                    detail={"vendor": drone.vendor},
                )
            )

        for asset in assets:
            point = telemetry.get(asset.bound_to_drone_id) if asset.bound_to_drone_id is not None else None
            items.append(
                MapLayerItemRead(
                    id=asset.id,
                    category="asset",
                    label=asset.name,
                    status=f"{asset.lifecycle_status.value}:{asset.availability_status.value}",
                    point=(
                        MapPointRead(lat=point.lat, lon=point.lon, alt_m=point.alt_m, ts=point.ts)
                        if point is not None
                        else None
                    ),
                    detail={
                        "asset_type": asset.asset_type.value,
                        "asset_code": asset.asset_code,
                        "bound_to_drone_id": asset.bound_to_drone_id,
                        "region_code": asset.region_code,
                    },
                )
            )
        return MapLayerRead(layer=MapLayerName.RESOURCES, total=len(items), items=items[:limit])

    def tasks_layer(self, tenant_id: str, *, viewer_user_id: str | None, limit: int = 100) -> MapLayerRead:
        with self._session() as session:
            scope = self._data_perimeter.resolve_scope(session, tenant_id, viewer_user_id)
            missions = [
                item
                for item in session.exec(select(Mission).where(Mission.tenant_id == tenant_id)).all()
                if self._data_perimeter.mission_visible(item, scope)
            ]
            inspection_tasks = [
                item
                for item in session.exec(select(InspectionTask).where(InspectionTask.tenant_id == tenant_id)).all()
                if self._data_perimeter.inspection_task_visible(item, scope)
            ]
            incidents = [
                item
                for item in session.exec(select(Incident).where(Incident.tenant_id == tenant_id)).all()
                if self._data_perimeter.incident_visible(item, scope)
            ]

        items: list[MapLayerItemRead] = []
        for mission in missions:
            items.append(
                MapLayerItemRead(
                    id=mission.id,
                    category="mission",
                    label=mission.name,
                    status=mission.state.value,
                    detail={
                        "drone_id": mission.drone_id,
                        "plan_type": mission.plan_type.value,
                        "project_code": mission.project_code,
                        "area_code": mission.area_code,
                        "updated_at": mission.updated_at.isoformat(),
                        "created_at": mission.created_at.isoformat(),
                    },
                )
            )
        for task in inspection_tasks:
            items.append(
                MapLayerItemRead(
                    id=task.id,
                    category="inspection_task",
                    label=task.name,
                    status=task.status.value,
                    point=self._parse_wkt_focus_point(task.area_geom),
                    detail={
                        "mission_id": task.mission_id,
                        "template_id": task.template_id,
                        "project_code": task.project_code,
                        "area_code": task.area_code,
                        "created_at": task.created_at.isoformat(),
                    },
                )
            )
        for incident in incidents:
            items.append(
                MapLayerItemRead(
                    id=incident.id,
                    category="incident",
                    label=incident.title,
                    status=incident.status.value,
                    point=self._parse_wkt_focus_point(incident.location_geom),
                    detail={
                        "level": incident.level,
                        "linked_task_id": incident.linked_task_id,
                        "project_code": incident.project_code,
                        "area_code": incident.area_code,
                        "created_at": incident.created_at.isoformat(),
                    },
                )
            )
        return MapLayerRead(layer=MapLayerName.TASKS, total=len(items), items=items[:limit])

    def airspace_layer(self, tenant_id: str, *, viewer_user_id: str | None, limit: int = 100) -> MapLayerRead:
        with self._session() as session:
            scope = self._data_perimeter.resolve_scope(session, tenant_id, viewer_user_id)
            rows = list(session.exec(select(AirspaceZone).where(AirspaceZone.tenant_id == tenant_id)).all())

        visible = [
            item
            for item in rows
            if self._data_perimeter.allows(
                scope,
                org_unit_id=item.org_unit_id,
                project_code=None,
                area_code=item.area_code,
                task_id=None,
            )
        ]
        items = [
            MapLayerItemRead(
                id=row.id,
                category="airspace",
                label=row.name,
                status="启用" if row.is_active else "停用",
                point=self._parse_wkt_focus_point(row.geom_wkt),
                detail={
                    "zone_type": row.zone_type.value,
                    "policy_layer": row.policy_layer.value,
                    "policy_effect": row.policy_effect.value,
                    "area_code": row.area_code,
                    "updated_at": row.updated_at.isoformat(),
                    "created_at": row.created_at.isoformat(),
                },
            )
            for row in visible
        ]
        return MapLayerRead(layer=MapLayerName.AIRSPACE, total=len(items), items=items[:limit])

    def alerts_layer(self, tenant_id: str, *, limit: int = 100) -> MapLayerRead:
        with self._session() as session:
            telemetry = self._latest_telemetry_by_drone(session, tenant_id)
            rows = list(session.exec(select(AlertRecord).where(AlertRecord.tenant_id == tenant_id)).all())

        alerts = sorted(
            [item for item in rows if item.status in {AlertStatus.OPEN, AlertStatus.ACKED}],
            key=lambda item: item.last_seen_at,
            reverse=True,
        )
        items: list[MapLayerItemRead] = []
        for alert in alerts:
            point = telemetry.get(alert.drone_id)
            items.append(
                MapLayerItemRead(
                    id=alert.id,
                    category="alert",
                    label=alert.message,
                    status=alert.status.value,
                    point=(
                        MapPointRead(lat=point.lat, lon=point.lon, alt_m=point.alt_m, ts=point.ts)
                        if point is not None
                        else None
                    ),
                    detail={
                        "drone_id": alert.drone_id,
                        "alert_type": alert.alert_type.value,
                        "severity": alert.severity.value,
                        "last_seen_at": alert.last_seen_at.isoformat(),
                        "first_seen_at": alert.first_seen_at.isoformat(),
                    },
                )
            )
        return MapLayerRead(layer=MapLayerName.ALERTS, total=len(items), items=items[:limit])

    def events_layer(self, tenant_id: str, *, viewer_user_id: str | None, limit: int = 100) -> MapLayerRead:
        with self._session() as session:
            scope = self._data_perimeter.resolve_scope(session, tenant_id, viewer_user_id)
            if not scope.is_all():
                return MapLayerRead(layer=MapLayerName.EVENTS, total=0, items=[])
            rows = list(session.exec(select(EventRecord).where(EventRecord.tenant_id == tenant_id)).all())
        rows = sorted(rows, key=lambda item: item.ts, reverse=True)

        interesting = [
            row
            for row in rows
            if row.event_type.startswith("alert.")
            or row.event_type.startswith("incident.")
            or row.event_type.startswith("mission.")
        ]
        items: list[MapLayerItemRead] = []
        for row in interesting:
            position = row.payload.get("position")
            point: MapPointRead | None = None
            if isinstance(position, dict):
                lat = position.get("lat")
                lon = position.get("lon")
                if isinstance(lat, int | float) and isinstance(lon, int | float):
                    alt_value = position.get("alt_m")
                    alt_m = float(alt_value) if isinstance(alt_value, int | float) else None
                    point = MapPointRead(lat=float(lat), lon=float(lon), alt_m=alt_m, ts=row.ts)
            items.append(
                MapLayerItemRead(
                    id=row.event_id,
                    category="event",
                    label=row.event_type,
                    status=None,
                    point=point,
                    detail={"payload": row.payload, "ts": row.ts.isoformat()},
                )
            )
        return MapLayerRead(layer=MapLayerName.EVENTS, total=len(items), items=items[:limit])

    def outcomes_layer(self, tenant_id: str, *, limit: int = 100) -> MapLayerRead:
        with self._session() as session:
            rows = list(session.exec(select(OutcomeCatalogRecord).where(OutcomeCatalogRecord.tenant_id == tenant_id)).all())

        ordered = sorted(rows, key=lambda item: item.updated_at, reverse=True)
        items = [
            MapLayerItemRead(
                id=row.id,
                category="outcome",
                label=f"{row.outcome_type.value} / {row.source_type.value}",
                status=row.status.value,
                point=(
                    MapPointRead(lat=row.point_lat, lon=row.point_lon, alt_m=row.alt_m)
                    if row.point_lat is not None and row.point_lon is not None
                    else None
                ),
                detail={
                    "outcome_type": row.outcome_type.value,
                    "source_type": row.source_type.value,
                    "source_id": row.source_id,
                    "task_id": row.task_id,
                    "mission_id": row.mission_id,
                    "confidence": row.confidence,
                    "updated_at": row.updated_at.isoformat(),
                    "created_at": row.created_at.isoformat(),
                },
            )
            for row in ordered
        ]
        return MapLayerRead(layer=MapLayerName.OUTCOMES, total=len(items), items=items[:limit])

    def overview(self, tenant_id: str, *, viewer_user_id: str | None, limit_per_layer: int = 100) -> MapOverviewRead:
        resources = self.resources_layer(tenant_id, limit=limit_per_layer)
        tasks = self.tasks_layer(tenant_id, viewer_user_id=viewer_user_id, limit=limit_per_layer)
        airspace = self.airspace_layer(tenant_id, viewer_user_id=viewer_user_id, limit=limit_per_layer)
        alerts = self.alerts_layer(tenant_id, limit=limit_per_layer)
        events = self.events_layer(tenant_id, viewer_user_id=viewer_user_id, limit=limit_per_layer)
        outcomes = self.outcomes_layer(tenant_id, limit=limit_per_layer)
        return MapOverviewRead(
            generated_at=datetime.now(UTC),
            resources_total=resources.total,
            tasks_total=tasks.total,
            airspace_total=airspace.total,
            alerts_total=alerts.total,
            events_total=events.total,
            outcomes_total=outcomes.total,
            layers=[resources, tasks, airspace, alerts, events, outcomes],
        )

    def replay_track(
        self,
        tenant_id: str,
        *,
        drone_id: str,
        from_ts: datetime | None = None,
        to_ts: datetime | None = None,
        sample_step: int = 1,
        limit: int = 500,
    ) -> MapTrackReplayRead:
        with self._session() as session:
            self._ensure_scoped_drone(session, tenant_id, drone_id)
            rows = list(
                session.exec(
                    select(EventRecord)
                    .where(EventRecord.tenant_id == tenant_id)
                    .where(EventRecord.event_type == "telemetry.normalized")
                ).all()
            )
        rows = sorted(rows, key=lambda item: item.ts)

        points: list[_TelemetryPoint] = []
        for row in rows:
            point = self._payload_to_telemetry(row.payload, row.ts)
            if point is None or point.drone_id != drone_id:
                continue
            if from_ts is not None and point.ts < from_ts:
                continue
            if to_ts is not None and point.ts > to_ts:
                continue
            points.append(point)

        if not points:
            raise NotFoundError("track replay not found")

        sampled = points[::sample_step]
        if len(sampled) > limit:
            sampled = sampled[-limit:]
        replay_points = [
            MapTrackPointRead(
                drone_id=item.drone_id,
                ts=item.ts,
                lat=item.lat,
                lon=item.lon,
                alt_m=item.alt_m,
                mode=item.mode,
            )
            for item in sampled
        ]
        return MapTrackReplayRead(
            drone_id=drone_id,
            from_ts=replay_points[0].ts if replay_points else None,
            to_ts=replay_points[-1].ts if replay_points else None,
            points=replay_points,
        )
