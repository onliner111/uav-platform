from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlmodel import Session, select

from app.domain.models import (
    AlertRecord,
    AlertSeverity,
    AlertStatus,
    AlertType,
    TelemetryNormalized,
)
from app.infra.db import get_engine
from app.infra.events import event_bus


@dataclass
class TriggeredAlert:
    alert_type: AlertType
    severity: AlertSeverity
    message: str
    detail: dict[str, Any]


class AlertError(Exception):
    pass


class NotFoundError(AlertError):
    pass


class ConflictError(AlertError):
    pass


class AlertService:
    LOW_BATTERY_THRESHOLD = 20.0

    def _session(self) -> Session:
        return Session(get_engine(), expire_on_commit=False)

    def _get_scoped_alert(
        self,
        session: Session,
        tenant_id: str,
        alert_id: str,
    ) -> AlertRecord | None:
        return session.exec(
            select(AlertRecord)
            .where(AlertRecord.tenant_id == tenant_id)
            .where(AlertRecord.id == alert_id)
        ).first()

    @staticmethod
    def _as_bool(value: object) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, int | float):
            return bool(value)
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return False

    def _rule_low_battery(self, payload: TelemetryNormalized) -> TriggeredAlert | None:
        in_health = self._as_bool(payload.health.get("low_battery"))
        percent = payload.battery.percent if payload.battery is not None else None
        threshold_hit = percent is not None and percent <= self.LOW_BATTERY_THRESHOLD
        if not in_health and not threshold_hit:
            return None
        return TriggeredAlert(
            alert_type=AlertType.LOW_BATTERY,
            severity=AlertSeverity.WARNING,
            message="Low battery detected",
            detail={"battery_percent": percent, "threshold": self.LOW_BATTERY_THRESHOLD},
        )

    def _rule_link_loss(self, payload: TelemetryNormalized) -> TriggeredAlert | None:
        in_health = self._as_bool(payload.health.get("link_lost"))
        weak_link = payload.link is not None and payload.link.rssi is None
        high_latency = (
            payload.link is not None
            and payload.link.latency_ms is not None
            and payload.link.latency_ms >= 2000
        )
        mode_flag = payload.mode.upper() == "LINK_LOST"
        if not (in_health or mode_flag or (weak_link and high_latency)):
            return None
        return TriggeredAlert(
            alert_type=AlertType.LINK_LOSS,
            severity=AlertSeverity.CRITICAL,
            message="Link loss detected",
            detail={"mode": payload.mode, "latency_ms": payload.link.latency_ms if payload.link else None},
        )

    def _rule_geofence_breach(self, payload: TelemetryNormalized) -> TriggeredAlert | None:
        in_health = self._as_bool(payload.health.get("geofence_breach"))
        if not in_health:
            return None
        return TriggeredAlert(
            alert_type=AlertType.GEOFENCE_BREACH,
            severity=AlertSeverity.CRITICAL,
            message="Geofence breach detected",
            detail={
                "position": payload.position.model_dump(mode="json"),
                "mode": payload.mode,
            },
        )

    def _evaluate_rules(self, payload: TelemetryNormalized) -> list[TriggeredAlert]:
        candidates = [
            self._rule_low_battery(payload),
            self._rule_link_loss(payload),
            self._rule_geofence_breach(payload),
        ]
        return [item for item in candidates if item is not None]

    def evaluate_telemetry(self, tenant_id: str, payload: TelemetryNormalized) -> list[AlertRecord]:
        triggered = self._evaluate_rules(payload)
        if not triggered:
            return []

        now = datetime.now(UTC)
        created: list[AlertRecord] = []
        with self._session() as session:
            existing = list(
                session.exec(
                    select(AlertRecord)
                    .where(AlertRecord.tenant_id == tenant_id)
                    .where(AlertRecord.drone_id == payload.drone_id)
                ).all()
            )
            active_by_type = {
                existing_alert.alert_type: existing_alert
                for existing_alert in existing
                if existing_alert.status in {AlertStatus.OPEN, AlertStatus.ACKED}
            }

            for triggered_alert in triggered:
                active = active_by_type.get(triggered_alert.alert_type)
                if active is not None:
                    active.last_seen_at = now
                    active.message = triggered_alert.message
                    active.detail = triggered_alert.detail
                    if (
                        active.severity != AlertSeverity.CRITICAL
                        and triggered_alert.severity == AlertSeverity.CRITICAL
                    ):
                        active.severity = AlertSeverity.CRITICAL
                    session.add(active)
                    continue

                record = AlertRecord(
                    tenant_id=tenant_id,
                    drone_id=payload.drone_id,
                    alert_type=triggered_alert.alert_type,
                    severity=triggered_alert.severity,
                    status=AlertStatus.OPEN,
                    message=triggered_alert.message,
                    detail=triggered_alert.detail,
                    first_seen_at=now,
                    last_seen_at=now,
                )
                session.add(record)
                created.append(record)

            session.commit()
            for created_alert in created:
                session.refresh(created_alert)

        for created_alert in created:
            event_bus.publish_dict(
                "alert.created",
                tenant_id,
                {
                    "alert_id": created_alert.id,
                    "drone_id": created_alert.drone_id,
                    "alert_type": created_alert.alert_type,
                    "severity": created_alert.severity,
                    "status": created_alert.status,
                },
            )
        return created

    def list_alerts(
        self,
        tenant_id: str,
        *,
        drone_id: str | None = None,
        status: AlertStatus | None = None,
    ) -> list[AlertRecord]:
        with self._session() as session:
            statement = select(AlertRecord).where(AlertRecord.tenant_id == tenant_id)
            if drone_id is not None:
                statement = statement.where(AlertRecord.drone_id == drone_id)
            if status is not None:
                statement = statement.where(AlertRecord.status == status)
            rows = list(session.exec(statement).all())
            return sorted(rows, key=lambda item: item.last_seen_at, reverse=True)

    def get_alert(self, tenant_id: str, alert_id: str) -> AlertRecord:
        with self._session() as session:
            record = self._get_scoped_alert(session, tenant_id, alert_id)
            if record is None:
                raise NotFoundError("alert not found")
            return record

    def ack_alert(
        self,
        tenant_id: str,
        alert_id: str,
        actor_id: str,
        *,
        comment: str | None = None,
    ) -> AlertRecord:
        published = False
        with self._session() as session:
            record = self._get_scoped_alert(session, tenant_id, alert_id)
            if record is None:
                raise NotFoundError("alert not found")
            if record.status == AlertStatus.CLOSED:
                raise ConflictError("alert already closed")

            if record.status != AlertStatus.ACKED:
                record.status = AlertStatus.ACKED
                record.acked_by = actor_id
                record.acked_at = datetime.now(UTC)
                published = True
            record.last_seen_at = datetime.now(UTC)
            if comment:
                detail = dict(record.detail)
                detail["ack_comment"] = comment
                record.detail = detail
            session.add(record)
            session.commit()
            session.refresh(record)

        if published:
            event_bus.publish_dict(
                "alert.acked",
                tenant_id,
                {
                    "alert_id": record.id,
                    "drone_id": record.drone_id,
                    "alert_type": record.alert_type,
                    "status": record.status,
                    "acked_by": record.acked_by,
                },
            )
        return record

    def close_alert(
        self,
        tenant_id: str,
        alert_id: str,
        actor_id: str,
        *,
        comment: str | None = None,
    ) -> AlertRecord:
        published = False
        with self._session() as session:
            record = self._get_scoped_alert(session, tenant_id, alert_id)
            if record is None:
                raise NotFoundError("alert not found")

            if record.status != AlertStatus.CLOSED:
                record.status = AlertStatus.CLOSED
                record.closed_by = actor_id
                record.closed_at = datetime.now(UTC)
                published = True
            record.last_seen_at = datetime.now(UTC)
            if comment:
                detail = dict(record.detail)
                detail["close_comment"] = comment
                record.detail = detail
            session.add(record)
            session.commit()
            session.refresh(record)

        if published:
            event_bus.publish_dict(
                "alert.closed",
                tenant_id,
                {
                    "alert_id": record.id,
                    "drone_id": record.drone_id,
                    "alert_type": record.alert_type,
                    "status": record.status,
                    "closed_by": record.closed_by,
                },
            )
        return record
