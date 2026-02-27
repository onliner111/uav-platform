from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import true
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.domain.models import (
    AlertAggregationRule,
    AlertAggregationRuleCreate,
    AlertEscalationExecution,
    AlertEscalationPolicy,
    AlertEscalationPolicyCreate,
    AlertEscalationReason,
    AlertEscalationRunItemRead,
    AlertEscalationRunRead,
    AlertEscalationRunRequest,
    AlertHandlingAction,
    AlertHandlingActionCreate,
    AlertHandlingActionType,
    AlertOncallShift,
    AlertOncallShiftCreate,
    AlertPriority,
    AlertRecord,
    AlertRouteChannel,
    AlertRouteDeliveryStatus,
    AlertRouteLog,
    AlertRouteReceiptRequest,
    AlertRouteStatus,
    AlertRoutingRule,
    AlertRoutingRuleCreate,
    AlertSeverity,
    AlertSilenceRule,
    AlertSilenceRuleCreate,
    AlertSlaOverviewRead,
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
    ONCALL_ACTIVE_TARGET = "oncall://active"

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

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    def _resolve_oncall_target(self, session: Session, tenant_id: str, at: datetime) -> str | None:
        at_utc = self._as_utc(at)
        shifts = list(
            session.exec(
                select(AlertOncallShift)
                .where(AlertOncallShift.tenant_id == tenant_id)
                .where(AlertOncallShift.is_active == true())
            ).all()
        )
        active = [
            item
            for item in shifts
            if self._as_utc(item.starts_at) <= at_utc < self._as_utc(item.ends_at)
        ]
        if not active:
            return None
        selected = sorted(active, key=lambda item: self._as_utc(item.starts_at), reverse=True)[0]
        return selected.target

    def _resolve_dynamic_target(
        self,
        session: Session,
        tenant_id: str,
        requested_target: str,
        at: datetime,
    ) -> str:
        if requested_target != self.ONCALL_ACTIVE_TARGET:
            return requested_target
        oncall_target = self._resolve_oncall_target(session, tenant_id, at)
        return oncall_target or "duty-default"

    @staticmethod
    def _optional_alert_type_match(rule_alert_type: AlertType | None, alert_type: AlertType) -> bool:
        return rule_alert_type is None or rule_alert_type == alert_type

    def _find_matching_silence_rule(
        self,
        session: Session,
        tenant_id: str,
        *,
        drone_id: str,
        alert_type: AlertType,
        at: datetime,
    ) -> AlertSilenceRule | None:
        rows = list(
            session.exec(
                select(AlertSilenceRule)
                .where(AlertSilenceRule.tenant_id == tenant_id)
                .where(AlertSilenceRule.is_active == true())
            ).all()
        )
        at_utc = self._as_utc(at)
        for rule in rows:
            if not self._optional_alert_type_match(rule.alert_type, alert_type):
                continue
            if rule.drone_id is not None and rule.drone_id != drone_id:
                continue
            if rule.starts_at is not None and at_utc < self._as_utc(rule.starts_at):
                continue
            if rule.ends_at is not None and at_utc >= self._as_utc(rule.ends_at):
                continue
            return rule
        return None

    def _find_matching_aggregation_rule(
        self,
        session: Session,
        tenant_id: str,
        *,
        alert_type: AlertType,
    ) -> AlertAggregationRule | None:
        rows = list(
            session.exec(
                select(AlertAggregationRule)
                .where(AlertAggregationRule.tenant_id == tenant_id)
                .where(AlertAggregationRule.is_active == true())
            ).all()
        )
        matched = [item for item in rows if self._optional_alert_type_match(item.alert_type, alert_type)]
        if not matched:
            return None
        return sorted(matched, key=lambda item: (item.alert_type is None, item.created_at))[0]

    def _dispatch_channel(
        self,
        tenant_id: str,
        alert: AlertRecord,
        *,
        channel: AlertRouteChannel,
        target: str,
        reason_hint: str,
    ) -> tuple[AlertRouteDeliveryStatus, dict[str, Any]]:
        if channel == AlertRouteChannel.IN_APP:
            return AlertRouteDeliveryStatus.SENT, {"delivery_mode": "in_app"}

        if channel == AlertRouteChannel.WEBHOOK:
            return AlertRouteDeliveryStatus.SENT, {
                "delivery_mode": "webhook_simulated",
                "webhook_dispatch_id": f"sim-{uuid4().hex[:16]}",
                "reason_hint": reason_hint,
                "target": target,
            }

        return AlertRouteDeliveryStatus.SKIPPED, {
            "delivery_mode": "placeholder",
            "reason": "external notification adapter placeholder",
        }

    def _get_scoped_route_log(
        self,
        session: Session,
        tenant_id: str,
        route_log_id: str,
    ) -> AlertRouteLog | None:
        return session.exec(
            select(AlertRouteLog)
            .where(AlertRouteLog.tenant_id == tenant_id)
            .where(AlertRouteLog.id == route_log_id)
        ).first()

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
                resolved_target = self._resolve_dynamic_target(session, tenant_id, rule.target, now)
                delivery_status, channel_detail = self._dispatch_channel(
                    tenant_id,
                    alert,
                    channel=rule.channel,
                    target=resolved_target,
                    reason_hint="route_dispatch",
                )
                route_log = AlertRouteLog(
                    tenant_id=tenant_id,
                    alert_id=alert.id,
                    rule_id=rule.id,
                    priority_level=alert.priority_level,
                    channel=rule.channel,
                    target=resolved_target,
                    delivery_status=delivery_status,
                    detail={
                        "rule_id": rule.id,
                        "auto": True,
                        "requested_target": rule.target,
                        "resolved_target": resolved_target,
                        **channel_detail,
                    },
                )
                session.add(route_log)
                targets.append({"channel": rule.channel.value, "target": resolved_target})
        else:
            fallback_target = self._resolve_dynamic_target(
                session,
                tenant_id,
                self.ONCALL_ACTIVE_TARGET,
                now,
            )
            default_log = AlertRouteLog(
                tenant_id=tenant_id,
                alert_id=alert.id,
                rule_id=None,
                priority_level=alert.priority_level,
                channel=AlertRouteChannel.IN_APP,
                target=fallback_target,
                delivery_status=AlertRouteDeliveryStatus.SENT,
                detail={
                    "fallback": True,
                    "requested_target": self.ONCALL_ACTIVE_TARGET,
                    "resolved_target": fallback_target,
                },
            )
            session.add(default_log)
            targets.append({"channel": AlertRouteChannel.IN_APP.value, "target": fallback_target})

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
        suppressed: list[dict[str, Any]] = []
        noise_suppressed: list[dict[str, Any]] = []
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
                silence_rule = self._find_matching_silence_rule(
                    session,
                    tenant_id,
                    drone_id=payload.drone_id,
                    alert_type=triggered_alert.alert_type,
                    at=now,
                )
                if silence_rule is not None:
                    suppressed.append(
                        {
                            "drone_id": payload.drone_id,
                            "alert_type": triggered_alert.alert_type.value,
                            "severity": triggered_alert.severity.value,
                            "silence_rule_id": silence_rule.id,
                            "silence_rule_name": silence_rule.name,
                        }
                    )
                    continue

                aggregation_rule = self._find_matching_aggregation_rule(
                    session,
                    tenant_id,
                    alert_type=triggered_alert.alert_type,
                )
                active = active_by_type.get(triggered_alert.alert_type)
                if active is not None:
                    previous_priority = active.priority_level
                    previous_detail = dict(active.detail)
                    previous_last_seen = active.last_seen_at
                    active.last_seen_at = now
                    active.message = triggered_alert.message
                    next_detail = dict(triggered_alert.detail)
                    previous_repeat_count = int(previous_detail.get("repeat_count", 1))
                    next_detail["repeat_count"] = previous_repeat_count + 1
                    if "routing" in previous_detail:
                        next_detail["routing"] = previous_detail["routing"]
                    if "escalation" in previous_detail:
                        next_detail["escalation"] = previous_detail["escalation"]
                    if "aggregation" in previous_detail:
                        next_detail["aggregation"] = previous_detail["aggregation"]
                    if aggregation_rule is not None:
                        elapsed_seconds = (
                            self._as_utc(now) - self._as_utc(previous_last_seen)
                        ).total_seconds()
                        if elapsed_seconds <= float(aggregation_rule.window_seconds):
                            prior_agg = previous_detail.get("aggregation", {})
                            aggregated_count = self._as_int(
                                prior_agg.get("aggregated_count")
                                if isinstance(prior_agg, dict)
                                else None
                            )
                            next_aggregated_count = aggregated_count + 1
                            next_detail["aggregation"] = {
                                "rule_id": aggregation_rule.id,
                                "rule_name": aggregation_rule.name,
                                "window_seconds": aggregation_rule.window_seconds,
                                "aggregated_count": next_aggregated_count,
                                "aggregated_at": now.isoformat(),
                            }
                            noise_threshold = self._as_int(
                                aggregation_rule.detail.get("noise_threshold")
                                if isinstance(aggregation_rule.detail, dict)
                                else None
                            )
                            if noise_threshold >= 2 and next_aggregated_count >= noise_threshold:
                                previous_noise = previous_detail.get("noise_control", {})
                                previous_noise_suppressed = (
                                    isinstance(previous_noise, dict)
                                    and self._as_bool(previous_noise.get("suppressed"))
                                )
                                next_detail["noise_control"] = {
                                    "suppressed": True,
                                    "reason": "repeat_threshold",
                                    "threshold": noise_threshold,
                                    "aggregated_count": next_aggregated_count,
                                    "at": now.isoformat(),
                                }
                                if not previous_noise_suppressed:
                                    noise_suppressed.append(
                                        {
                                            "alert_id": active.id,
                                            "drone_id": active.drone_id,
                                            "alert_type": active.alert_type.value,
                                            "threshold": noise_threshold,
                                            "aggregated_count": next_aggregated_count,
                                        }
                                    )
                    active.detail = next_detail
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
                    detail={**triggered_alert.detail, "repeat_count": 1},
                    first_seen_at=now,
                    last_seen_at=now,
                )
                if aggregation_rule is not None:
                    detail = dict(record.detail)
                    detail["aggregation"] = {
                        "rule_id": aggregation_rule.id,
                        "rule_name": aggregation_rule.name,
                        "window_seconds": aggregation_rule.window_seconds,
                        "aggregated_count": 0,
                    }
                    record.detail = detail
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
        for suppressed_item in suppressed:
            event_bus.publish_dict("alert.suppressed", tenant_id, suppressed_item)
        for noise_item in noise_suppressed:
            event_bus.publish_dict("alert.noise_suppressed", tenant_id, noise_item)
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

    def create_silence_rule(
        self,
        tenant_id: str,
        actor_id: str,
        payload: AlertSilenceRuleCreate,
    ) -> AlertSilenceRule:
        starts_at = self._as_utc(payload.starts_at) if payload.starts_at is not None else None
        ends_at = self._as_utc(payload.ends_at) if payload.ends_at is not None else None
        if starts_at is not None and ends_at is not None and ends_at <= starts_at:
            raise ConflictError("silence rule window invalid")
        with self._session() as session:
            row = AlertSilenceRule(
                tenant_id=tenant_id,
                name=payload.name,
                alert_type=payload.alert_type,
                drone_id=payload.drone_id,
                starts_at=starts_at,
                ends_at=ends_at,
                is_active=payload.is_active,
                detail=payload.detail,
                created_by=actor_id,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return row

    def list_silence_rules(
        self,
        tenant_id: str,
        *,
        is_active: bool | None = None,
    ) -> list[AlertSilenceRule]:
        with self._session() as session:
            statement = select(AlertSilenceRule).where(AlertSilenceRule.tenant_id == tenant_id)
            if is_active is not None:
                statement = statement.where(AlertSilenceRule.is_active == is_active)
            rows = list(session.exec(statement).all())
            return sorted(rows, key=lambda item: item.created_at, reverse=True)

    def create_aggregation_rule(
        self,
        tenant_id: str,
        actor_id: str,
        payload: AlertAggregationRuleCreate,
    ) -> AlertAggregationRule:
        with self._session() as session:
            row = AlertAggregationRule(
                tenant_id=tenant_id,
                name=payload.name,
                alert_type=payload.alert_type,
                window_seconds=payload.window_seconds,
                is_active=payload.is_active,
                detail=payload.detail,
                created_by=actor_id,
            )
            session.add(row)
            try:
                session.commit()
            except IntegrityError as exc:
                session.rollback()
                raise ConflictError("alert aggregation rule create conflict") from exc
            session.refresh(row)
            return row

    def list_aggregation_rules(
        self,
        tenant_id: str,
        *,
        is_active: bool | None = None,
    ) -> list[AlertAggregationRule]:
        with self._session() as session:
            statement = select(AlertAggregationRule).where(AlertAggregationRule.tenant_id == tenant_id)
            if is_active is not None:
                statement = statement.where(AlertAggregationRule.is_active == is_active)
            rows = list(session.exec(statement).all())
            return sorted(rows, key=lambda item: item.created_at, reverse=True)

    def create_oncall_shift(
        self,
        tenant_id: str,
        actor_id: str,
        payload: AlertOncallShiftCreate,
    ) -> AlertOncallShift:
        starts_at = self._as_utc(payload.starts_at)
        ends_at = self._as_utc(payload.ends_at)
        if ends_at <= starts_at:
            raise ConflictError("oncall shift window invalid")
        with self._session() as session:
            row = AlertOncallShift(
                tenant_id=tenant_id,
                shift_name=payload.shift_name,
                target=payload.target,
                starts_at=starts_at,
                ends_at=ends_at,
                timezone=payload.timezone,
                is_active=payload.is_active,
                detail=payload.detail,
                created_by=actor_id,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return row

    def list_oncall_shifts(
        self,
        tenant_id: str,
        *,
        active_at: datetime | None = None,
        is_active: bool | None = None,
    ) -> list[AlertOncallShift]:
        with self._session() as session:
            statement = select(AlertOncallShift).where(AlertOncallShift.tenant_id == tenant_id)
            if is_active is not None:
                statement = statement.where(AlertOncallShift.is_active == is_active)
            rows = list(session.exec(statement).all())
            if active_at is not None:
                active_at_utc = self._as_utc(active_at)
                rows = [
                    item
                    for item in rows
                    if self._as_utc(item.starts_at) <= active_at_utc < self._as_utc(item.ends_at)
                ]
            return sorted(rows, key=lambda item: item.starts_at, reverse=True)

    def create_escalation_policy(
        self,
        tenant_id: str,
        actor_id: str,
        payload: AlertEscalationPolicyCreate,
    ) -> AlertEscalationPolicy:
        with self._session() as session:
            existing = session.exec(
                select(AlertEscalationPolicy)
                .where(AlertEscalationPolicy.tenant_id == tenant_id)
                .where(AlertEscalationPolicy.priority_level == payload.priority_level)
            ).first()
            if existing is not None:
                existing.ack_timeout_seconds = payload.ack_timeout_seconds
                existing.repeat_threshold = payload.repeat_threshold
                existing.max_escalation_level = payload.max_escalation_level
                existing.escalation_channel = payload.escalation_channel
                existing.escalation_target = payload.escalation_target
                existing.is_active = payload.is_active
                existing.detail = payload.detail
                existing.updated_at = datetime.now(UTC)
                session.add(existing)
                session.commit()
                session.refresh(existing)
                return existing

            row = AlertEscalationPolicy(
                tenant_id=tenant_id,
                priority_level=payload.priority_level,
                ack_timeout_seconds=payload.ack_timeout_seconds,
                repeat_threshold=payload.repeat_threshold,
                max_escalation_level=payload.max_escalation_level,
                escalation_channel=payload.escalation_channel,
                escalation_target=payload.escalation_target,
                is_active=payload.is_active,
                detail=payload.detail,
                created_by=actor_id,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return row

    def list_escalation_policies(
        self,
        tenant_id: str,
        *,
        is_active: bool | None = None,
    ) -> list[AlertEscalationPolicy]:
        with self._session() as session:
            statement = select(AlertEscalationPolicy).where(AlertEscalationPolicy.tenant_id == tenant_id)
            if is_active is not None:
                statement = statement.where(AlertEscalationPolicy.is_active == is_active)
            rows = list(session.exec(statement).all())
            return sorted(rows, key=lambda item: item.priority_level.value)

    @staticmethod
    def _as_int(value: object, *, default: int = 0) -> int:
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            try:
                return int(value)
            except ValueError:
                return default
        return default

    def _latest_route_target(
        self,
        session: Session,
        tenant_id: str,
        alert_id: str,
        alert_detail: dict[str, Any],
    ) -> str | None:
        rows = list(
            session.exec(
                select(AlertRouteLog)
                .where(AlertRouteLog.tenant_id == tenant_id)
                .where(AlertRouteLog.alert_id == alert_id)
            ).all()
        )
        if rows:
            latest = sorted(rows, key=lambda item: item.created_at)[-1]
            return latest.target
        routing = alert_detail.get("routing", {})
        if isinstance(routing, dict):
            targets = routing.get("targets")
            if isinstance(targets, list) and targets:
                first = targets[0]
                if isinstance(first, dict):
                    target = first.get("target")
                    if isinstance(target, str):
                        return target
        return None

    def _build_escalation_decision(
        self,
        session: Session,
        tenant_id: str,
        alert: AlertRecord,
        policy: AlertEscalationPolicy,
        now: datetime,
    ) -> tuple[AlertEscalationReason, str | None, str, int] | None:
        detail = dict(alert.detail)
        current_target = self._latest_route_target(session, tenant_id, alert.id, detail)
        current_level = self._as_int(
            detail.get("escalation", {}).get("level") if isinstance(detail.get("escalation"), dict) else None
        )

        active_oncall_target = self._resolve_dynamic_target(
            session,
            tenant_id,
            self.ONCALL_ACTIVE_TARGET,
            now,
        )
        if current_target and current_target != active_oncall_target:
            level = max(current_level, 1)
            return (
                AlertEscalationReason.SHIFT_HANDOVER,
                current_target,
                active_oncall_target,
                level,
            )

        base_at = alert.routed_at or alert.first_seen_at
        elapsed_seconds = (self._as_utc(now) - self._as_utc(base_at)).total_seconds()
        if elapsed_seconds >= float(policy.ack_timeout_seconds):
            next_level = current_level + 1
            if next_level <= policy.max_escalation_level:
                return (
                    AlertEscalationReason.ACK_TIMEOUT,
                    current_target,
                    self._resolve_dynamic_target(
                        session,
                        tenant_id,
                        policy.escalation_target,
                        now,
                    ),
                    next_level,
                )

        repeat_count = self._as_int(detail.get("repeat_count"), default=1)
        if repeat_count >= policy.repeat_threshold:
            next_level = current_level + 1
            if next_level <= policy.max_escalation_level:
                return (
                    AlertEscalationReason.REPEAT_TRIGGER,
                    current_target,
                    self._resolve_dynamic_target(
                        session,
                        tenant_id,
                        policy.escalation_target,
                        now,
                    ),
                    next_level,
                )
        return None

    def run_alert_escalation(
        self,
        tenant_id: str,
        payload: AlertEscalationRunRequest,
    ) -> AlertEscalationRunRead:
        now = datetime.now(UTC)
        executed_events: list[dict[str, Any]] = []
        with self._session() as session:
            policy_rows = list(
                session.exec(
                    select(AlertEscalationPolicy)
                    .where(AlertEscalationPolicy.tenant_id == tenant_id)
                    .where(AlertEscalationPolicy.is_active == true())
                ).all()
            )
            policy_by_priority = {item.priority_level: item for item in policy_rows}

            alerts = list(
                session.exec(
                    select(AlertRecord)
                    .where(AlertRecord.tenant_id == tenant_id)
                    .where(AlertRecord.status == AlertStatus.OPEN)
                    .limit(payload.limit)
                ).all()
            )
            items: list[AlertEscalationRunItemRead] = []
            for alert in alerts:
                policy = policy_by_priority.get(alert.priority_level)
                if policy is None:
                    continue
                decision = self._build_escalation_decision(session, tenant_id, alert, policy, now)
                if decision is None:
                    continue
                reason, from_target, to_target, escalation_level = decision

                existing = session.exec(
                    select(AlertEscalationExecution)
                    .where(AlertEscalationExecution.tenant_id == tenant_id)
                    .where(AlertEscalationExecution.alert_id == alert.id)
                    .where(AlertEscalationExecution.escalation_level == escalation_level)
                ).first()
                if existing is not None:
                    continue

                run_item = AlertEscalationRunItemRead(
                    alert_id=alert.id,
                    reason=reason,
                    channel=policy.escalation_channel,
                    from_target=from_target,
                    to_target=to_target,
                    escalation_level=escalation_level,
                )
                items.append(run_item)
                if payload.dry_run:
                    continue

                delivery_status, channel_detail = self._dispatch_channel(
                    tenant_id,
                    alert,
                    channel=policy.escalation_channel,
                    target=to_target,
                    reason_hint=reason.value,
                )
                session.add(
                    AlertRouteLog(
                        tenant_id=tenant_id,
                        alert_id=alert.id,
                        rule_id=None,
                        priority_level=alert.priority_level,
                        channel=policy.escalation_channel,
                        target=to_target,
                        delivery_status=delivery_status,
                        detail={
                            "escalation": True,
                            "reason": reason.value,
                            "requested_target": policy.escalation_target,
                            "from_target": from_target,
                            "resolved_target": to_target,
                            **channel_detail,
                        },
                    )
                )
                session.add(
                    AlertEscalationExecution(
                        tenant_id=tenant_id,
                        alert_id=alert.id,
                        reason=reason,
                        escalation_level=escalation_level,
                        channel=policy.escalation_channel,
                        from_target=from_target,
                        to_target=to_target,
                        detail={"ack_timeout_seconds": policy.ack_timeout_seconds},
                    )
                )
                alert.route_status = AlertRouteStatus.ROUTED
                alert.routed_at = now
                alert.last_seen_at = now
                detail = dict(alert.detail)
                detail["escalation"] = {
                    "level": escalation_level,
                    "reason": reason.value,
                    "escalated_at": now.isoformat(),
                    "target": to_target,
                }
                alert.detail = detail
                session.add(alert)
                self._append_action(
                    session,
                    tenant_id=tenant_id,
                    alert_id=alert.id,
                    action_type=AlertHandlingActionType.ESCALATE,
                    actor_id="system",
                    note=f"alert escalated by {reason.value}",
                    detail={
                        "reason": reason.value,
                        "from_target": from_target,
                        "to_target": to_target,
                        "escalation_level": escalation_level,
                        "channel": policy.escalation_channel.value,
                    },
                )
                executed_events.append(
                    {
                        "alert_id": alert.id,
                        "reason": reason.value,
                        "escalation_level": escalation_level,
                        "target": to_target,
                    }
                )

            if not payload.dry_run and items:
                session.commit()

            result = AlertEscalationRunRead(
                scanned_count=len(alerts),
                escalated_count=len(items),
                dry_run=payload.dry_run,
                items=items,
            )

        if not payload.dry_run:
            for item in executed_events:
                event_bus.publish_dict("alert.escalated", tenant_id, item)
        return result

    def record_alert_route_receipt(
        self,
        tenant_id: str,
        route_log_id: str,
        actor_id: str,
        payload: AlertRouteReceiptRequest,
    ) -> AlertRouteLog:
        with self._session() as session:
            route_log = self._get_scoped_route_log(session, tenant_id, route_log_id)
            if route_log is None:
                raise NotFoundError("alert route log not found")
            route_log.delivery_status = payload.delivery_status
            detail = dict(route_log.detail)
            detail["receipt"] = {
                "receipt_id": payload.receipt_id,
                "actor_id": actor_id,
                "updated_at": datetime.now(UTC).isoformat(),
                **payload.detail,
            }
            route_log.detail = detail
            session.add(route_log)
            session.commit()
            session.refresh(route_log)

        event_bus.publish_dict(
            "alert.route.receipt",
            tenant_id,
            {
                "route_log_id": route_log.id,
                "alert_id": route_log.alert_id,
                "delivery_status": route_log.delivery_status.value,
            },
        )
        return route_log

    def get_alert_sla_overview(
        self,
        tenant_id: str,
        *,
        from_ts: datetime | None = None,
        to_ts: datetime | None = None,
    ) -> AlertSlaOverviewRead:
        from_ts_utc = self._as_utc(from_ts) if from_ts is not None else None
        to_ts_utc = self._as_utc(to_ts) if to_ts is not None else None
        with self._session() as session:
            statement = select(AlertRecord).where(AlertRecord.tenant_id == tenant_id)
            if from_ts_utc is not None:
                statement = statement.where(AlertRecord.first_seen_at >= from_ts_utc)
            if to_ts_utc is not None:
                statement = statement.where(AlertRecord.first_seen_at <= to_ts_utc)
            alerts = list(session.exec(statement).all())

            escalation_statement = (
                select(AlertEscalationExecution)
                .where(AlertEscalationExecution.tenant_id == tenant_id)
                .where(AlertEscalationExecution.reason == AlertEscalationReason.ACK_TIMEOUT)
            )
            if from_ts_utc is not None:
                escalation_statement = escalation_statement.where(
                    AlertEscalationExecution.created_at >= from_ts_utc
                )
            if to_ts_utc is not None:
                escalation_statement = escalation_statement.where(AlertEscalationExecution.created_at <= to_ts_utc)
            timeout_escalations = list(session.exec(escalation_statement).all())

        total_alerts = len(alerts)
        acked_alerts = len([item for item in alerts if item.acked_at is not None])
        closed_alerts = len([item for item in alerts if item.closed_at is not None])
        ack_durations = [
            (self._as_utc(item.acked_at) - self._as_utc(item.first_seen_at)).total_seconds()
            for item in alerts
            if item.acked_at is not None
        ]
        close_durations = [
            (self._as_utc(item.closed_at) - self._as_utc(item.first_seen_at)).total_seconds()
            for item in alerts
            if item.closed_at is not None
        ]
        timeout_escalated_alerts = len({item.alert_id for item in timeout_escalations})
        mtta_seconds_avg = (sum(ack_durations) / len(ack_durations)) if ack_durations else 0.0
        mttr_seconds_avg = (sum(close_durations) / len(close_durations)) if close_durations else 0.0
        timeout_escalation_rate = (
            timeout_escalated_alerts / total_alerts if total_alerts else 0.0
        )
        return AlertSlaOverviewRead(
            from_ts=from_ts_utc,
            to_ts=to_ts_utc,
            total_alerts=total_alerts,
            acked_alerts=acked_alerts,
            closed_alerts=closed_alerts,
            timeout_escalated_alerts=timeout_escalated_alerts,
            mtta_seconds_avg=mtta_seconds_avg,
            mttr_seconds_avg=mttr_seconds_avg,
            timeout_escalation_rate=timeout_escalation_rate,
        )

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
