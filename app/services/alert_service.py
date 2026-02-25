from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import true
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.domain.models import (
    AlertHandlingAction,
    AlertHandlingActionCreate,
    AlertHandlingActionType,
    AlertPriority,
    AlertRecord,
    AlertRouteChannel,
    AlertRouteDeliveryStatus,
    AlertRouteLog,
    AlertRouteStatus,
    AlertRoutingRule,
    AlertRoutingRuleCreate,
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

    @staticmethod
    def _resolve_priority(alert_type: AlertType, severity: AlertSeverity) -> AlertPriority:
        if alert_type in {AlertType.LINK_LOSS, AlertType.GEOFENCE_BREACH}:
            return AlertPriority.P1
        if severity == AlertSeverity.CRITICAL:
            return AlertPriority.P2
        return AlertPriority.P3

    def _dispatch_routes(self, session: Session, tenant_id: str, alert: AlertRecord) -> None:
        rules = list(
            session.exec(
                select(AlertRoutingRule)
                .where(AlertRoutingRule.tenant_id == tenant_id)
                .where(AlertRoutingRule.is_active == true())
                .where(AlertRoutingRule.priority_level == alert.priority_level)
            ).all()
        )
        matched = [item for item in rules if item.alert_type in {None, alert.alert_type}]
        now = datetime.now(UTC)
        targets: list[dict[str, str]] = []

        if matched:
            for rule in matched:
                is_in_app = rule.channel == AlertRouteChannel.IN_APP
                route_log = AlertRouteLog(
                    tenant_id=tenant_id,
                    alert_id=alert.id,
                    rule_id=rule.id,
                    priority_level=alert.priority_level,
                    channel=rule.channel,
                    target=rule.target,
                    delivery_status=(
                        AlertRouteDeliveryStatus.SENT
                        if is_in_app
                        else AlertRouteDeliveryStatus.SKIPPED
                    ),
                    detail=(
                        {"rule_id": rule.id, "auto": True}
                        if is_in_app
                        else {
                            "rule_id": rule.id,
                            "auto": True,
                            "reason": "external notification adapter placeholder",
                        }
                    ),
                )
                session.add(route_log)
                targets.append({"channel": rule.channel.value, "target": rule.target})
        else:
            default_log = AlertRouteLog(
                tenant_id=tenant_id,
                alert_id=alert.id,
                rule_id=None,
                priority_level=alert.priority_level,
                channel=AlertRouteChannel.IN_APP,
                target="duty-default",
                delivery_status=AlertRouteDeliveryStatus.SENT,
                detail={"fallback": True},
            )
            session.add(default_log)
            targets.append({"channel": AlertRouteChannel.IN_APP.value, "target": "duty-default"})

        alert.route_status = AlertRouteStatus.ROUTED
        alert.routed_at = now
        next_detail = dict(alert.detail)
        next_detail["routing"] = {
            "priority_level": alert.priority_level.value,
            "targets": targets,
            "routed_at": now.isoformat(),
        }
        alert.detail = next_detail
        session.add(alert)
        self._append_action(
            session,
            tenant_id=tenant_id,
            alert_id=alert.id,
            action_type=AlertHandlingActionType.DISPATCH,
            actor_id="system",
            note="alert routed",
            detail={"priority_level": alert.priority_level.value, "targets": targets},
        )

    def _append_action(
        self,
        session: Session,
        *,
        tenant_id: str,
        alert_id: str,
        action_type: AlertHandlingActionType,
        actor_id: str | None,
        note: str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> AlertHandlingAction:
        row = AlertHandlingAction(
            tenant_id=tenant_id,
            alert_id=alert_id,
            action_type=action_type,
            note=note,
            actor_id=actor_id,
            detail=detail or {},
        )
        session.add(row)
        return row

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
        routed: list[AlertRecord] = []
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
                    previous_priority = active.priority_level
                    active.last_seen_at = now
                    active.message = triggered_alert.message
                    active.detail = triggered_alert.detail
                    if (
                        active.severity != AlertSeverity.CRITICAL
                        and triggered_alert.severity == AlertSeverity.CRITICAL
                    ):
                        active.severity = AlertSeverity.CRITICAL
                    active.priority_level = self._resolve_priority(active.alert_type, active.severity)
                    if previous_priority != active.priority_level:
                        self._dispatch_routes(session, tenant_id, active)
                        routed.append(active)
                    session.add(active)
                    continue

                record = AlertRecord(
                    tenant_id=tenant_id,
                    drone_id=payload.drone_id,
                    alert_type=triggered_alert.alert_type,
                    severity=triggered_alert.severity,
                    priority_level=self._resolve_priority(
                        triggered_alert.alert_type,
                        triggered_alert.severity,
                    ),
                    status=AlertStatus.OPEN,
                    route_status=AlertRouteStatus.UNROUTED,
                    message=triggered_alert.message,
                    detail=triggered_alert.detail,
                    first_seen_at=now,
                    last_seen_at=now,
                )
                session.add(record)
                self._dispatch_routes(session, tenant_id, record)
                created.append(record)
                routed.append(record)

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
                    "priority_level": created_alert.priority_level,
                    "status": created_alert.status,
                },
            )
        for routed_alert in routed:
            event_bus.publish_dict(
                "alert.routed",
                tenant_id,
                {
                    "alert_id": routed_alert.id,
                    "alert_type": routed_alert.alert_type,
                    "priority_level": routed_alert.priority_level,
                    "route_status": routed_alert.route_status,
                },
            )
        return created

    def create_routing_rule(
        self,
        tenant_id: str,
        actor_id: str,
        payload: AlertRoutingRuleCreate,
    ) -> AlertRoutingRule:
        with self._session() as session:
            row = AlertRoutingRule(
                tenant_id=tenant_id,
                priority_level=payload.priority_level,
                alert_type=payload.alert_type,
                channel=payload.channel,
                target=payload.target,
                is_active=payload.is_active,
                detail=payload.detail,
                created_by=actor_id,
            )
            session.add(row)
            try:
                session.commit()
            except IntegrityError as exc:
                session.rollback()
                raise ConflictError("alert routing rule create conflict") from exc
            session.refresh(row)
            return row

    def list_routing_rules(
        self,
        tenant_id: str,
        *,
        priority_level: AlertPriority | None = None,
        alert_type: AlertType | None = None,
        is_active: bool | None = None,
    ) -> list[AlertRoutingRule]:
        with self._session() as session:
            statement = select(AlertRoutingRule).where(AlertRoutingRule.tenant_id == tenant_id)
            if priority_level is not None:
                statement = statement.where(AlertRoutingRule.priority_level == priority_level)
            if alert_type is not None:
                statement = statement.where(AlertRoutingRule.alert_type == alert_type)
            if is_active is not None:
                statement = statement.where(AlertRoutingRule.is_active == is_active)
            return list(session.exec(statement).all())

    def list_alert_routes(self, tenant_id: str, alert_id: str) -> list[AlertRouteLog]:
        with self._session() as session:
            record = self._get_scoped_alert(session, tenant_id, alert_id)
            if record is None:
                raise NotFoundError("alert not found")
            statement = (
                select(AlertRouteLog)
                .where(AlertRouteLog.tenant_id == tenant_id)
                .where(AlertRouteLog.alert_id == alert_id)
            )
            rows = list(session.exec(statement).all())
            return sorted(rows, key=lambda item: item.created_at)

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
            self._append_action(
                session,
                tenant_id=tenant_id,
                alert_id=record.id,
                action_type=AlertHandlingActionType.ACK,
                actor_id=actor_id,
                note=comment,
                detail={"status": record.status.value},
            )
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
            self._append_action(
                session,
                tenant_id=tenant_id,
                alert_id=record.id,
                action_type=AlertHandlingActionType.CLOSE,
                actor_id=actor_id,
                note=comment,
                detail={"status": record.status.value},
            )
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

    def create_handling_action(
        self,
        tenant_id: str,
        alert_id: str,
        actor_id: str,
        payload: AlertHandlingActionCreate,
    ) -> AlertHandlingAction:
        with self._session() as session:
            record = self._get_scoped_alert(session, tenant_id, alert_id)
            if record is None:
                raise NotFoundError("alert not found")
            row = self._append_action(
                session,
                tenant_id=tenant_id,
                alert_id=alert_id,
                action_type=payload.action_type,
                actor_id=actor_id,
                note=payload.note,
                detail=payload.detail,
            )
            session.commit()
            session.refresh(row)
            return row

    def list_handling_actions(self, tenant_id: str, alert_id: str) -> list[AlertHandlingAction]:
        with self._session() as session:
            record = self._get_scoped_alert(session, tenant_id, alert_id)
            if record is None:
                raise NotFoundError("alert not found")
            rows = list(
                session.exec(
                    select(AlertHandlingAction)
                    .where(AlertHandlingAction.tenant_id == tenant_id)
                    .where(AlertHandlingAction.alert_id == alert_id)
                ).all()
            )
            return sorted(rows, key=lambda item: item.created_at)

    def get_alert_review(
        self,
        tenant_id: str,
        alert_id: str,
    ) -> tuple[AlertRecord, list[AlertRouteLog], list[AlertHandlingAction]]:
        with self._session() as session:
            record = self._get_scoped_alert(session, tenant_id, alert_id)
            if record is None:
                raise NotFoundError("alert not found")
            routes = self.list_alert_routes(tenant_id, alert_id)
            actions = self.list_handling_actions(tenant_id, alert_id)
            return record, routes, actions
