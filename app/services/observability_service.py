from __future__ import annotations

import hashlib
import json
import math
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, select

from app.domain.models import (
    CapacityDecision,
    CapacityForecast,
    CapacityForecastRequest,
    CapacityPolicy,
    CapacityPolicyUpsertRequest,
    ObservabilityAlertEvent,
    ObservabilityAlertSeverity,
    ObservabilityAlertStatus,
    ObservabilityOverviewRead,
    ObservabilitySignal,
    ObservabilitySignalIngestRequest,
    ObservabilitySignalLevel,
    ObservabilitySignalType,
    ObservabilitySloEvaluateRequest,
    ObservabilitySloEvaluation,
    ObservabilitySloEvaluationRead,
    ObservabilitySloOverviewRead,
    ObservabilitySloPolicy,
    ObservabilitySloPolicyCreate,
    ObservabilitySloStatus,
    ReliabilityBackupRun,
    ReliabilityBackupRunRequest,
    ReliabilityBackupRunStatus,
    ReliabilityRestoreDrill,
    ReliabilityRestoreDrillRequest,
    ReliabilityRestoreDrillStatus,
    SecurityInspectionCheckStatus,
    SecurityInspectionItem,
    SecurityInspectionRun,
    SecurityInspectionRunRequest,
    User,
    now_utc,
)
from app.infra.db import get_engine


class ObservabilityError(Exception):
    pass


class NotFoundError(ObservabilityError):
    pass


class ConflictError(ObservabilityError):
    pass


class ObservabilityService:
    def _session(self) -> Session:
        return Session(get_engine(), expire_on_commit=False)

    @staticmethod
    def _normalize_non_empty(value: str, field_name: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ConflictError(f"{field_name} cannot be empty")
        return normalized

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    @staticmethod
    def _p95(values: list[int]) -> int | None:
        if not values:
            return None
        sorted_values = sorted(values)
        index = max(0, math.ceil(len(sorted_values) * 0.95) - 1)
        return int(sorted_values[index])

    def ingest_signals(
        self,
        tenant_id: str,
        actor_id: str,
        payload: ObservabilitySignalIngestRequest,
    ) -> list[ObservabilitySignal]:
        rows: list[ObservabilitySignal] = []
        with self._session() as session:
            for item in payload.items:
                service_name = self._normalize_non_empty(item.service_name, "service_name")
                signal_name = self._normalize_non_empty(item.signal_name, "signal_name")
                row = ObservabilitySignal(
                    tenant_id=tenant_id,
                    signal_type=item.signal_type,
                    level=item.level,
                    service_name=service_name,
                    signal_name=signal_name,
                    trace_id=item.trace_id.strip() if item.trace_id else None,
                    span_id=item.span_id.strip() if item.span_id else None,
                    status_code=item.status_code,
                    duration_ms=item.duration_ms,
                    numeric_value=item.numeric_value,
                    unit=item.unit.strip() if item.unit else None,
                    message=item.message,
                    detail=item.detail,
                    created_by=actor_id,
                    created_at=self._as_utc(item.occurred_at),
                )
                rows.append(row)
                session.add(row)
            try:
                session.commit()
            except IntegrityError as exc:
                session.rollback()
                raise ConflictError("failed to ingest observability signals") from exc
            for row in rows:
                session.refresh(row)
        return rows

    def list_signals(
        self,
        tenant_id: str,
        *,
        signal_type: ObservabilitySignalType | None = None,
        level: ObservabilitySignalLevel | None = None,
        service_name: str | None = None,
        signal_name: str | None = None,
        trace_id: str | None = None,
        from_ts: datetime | None = None,
        to_ts: datetime | None = None,
        limit: int = 100,
    ) -> list[ObservabilitySignal]:
        scoped_limit = min(max(limit, 1), 1000)
        with self._session() as session:
            statement = select(ObservabilitySignal).where(ObservabilitySignal.tenant_id == tenant_id)
            if signal_type is not None:
                statement = statement.where(ObservabilitySignal.signal_type == signal_type)
            if level is not None:
                statement = statement.where(ObservabilitySignal.level == level)
            if service_name is not None:
                statement = statement.where(ObservabilitySignal.service_name == service_name.strip())
            if signal_name is not None:
                statement = statement.where(ObservabilitySignal.signal_name == signal_name.strip())
            if trace_id is not None:
                statement = statement.where(ObservabilitySignal.trace_id == trace_id.strip())
            if from_ts is not None:
                statement = statement.where(ObservabilitySignal.created_at >= self._as_utc(from_ts))
            if to_ts is not None:
                statement = statement.where(ObservabilitySignal.created_at <= self._as_utc(to_ts))
            rows = list(session.exec(statement).all())
        rows_sorted = sorted(rows, key=lambda item: item.created_at, reverse=True)
        return rows_sorted[:scoped_limit]

    def get_overview(self, tenant_id: str, *, window_minutes: int = 60) -> ObservabilityOverviewRead:
        scoped_window = min(max(window_minutes, 1), 1440)
        from_ts = now_utc() - timedelta(minutes=scoped_window)
        rows = self.list_signals(
            tenant_id,
            from_ts=from_ts,
            limit=1000,
        )
        by_type = {
            ObservabilitySignalType.LOG.value: 0,
            ObservabilitySignalType.METRIC.value: 0,
            ObservabilitySignalType.TRACE.value: 0,
        }
        by_level = {
            ObservabilitySignalLevel.DEBUG.value: 0,
            ObservabilitySignalLevel.INFO.value: 0,
            ObservabilitySignalLevel.WARN.value: 0,
            ObservabilitySignalLevel.ERROR.value: 0,
        }
        error_signals = 0
        latency_values: list[int] = []
        for row in rows:
            by_type[row.signal_type.value] = by_type.get(row.signal_type.value, 0) + 1
            by_level[row.level.value] = by_level.get(row.level.value, 0) + 1
            if row.level == ObservabilitySignalLevel.ERROR or (row.status_code is not None and row.status_code >= 500):
                error_signals += 1
            if row.duration_ms is not None:
                latency_values.append(row.duration_ms)
        return ObservabilityOverviewRead(
            window_minutes=scoped_window,
            total_signals=len(rows),
            error_signals=error_signals,
            p95_latency_ms=self._p95(latency_values),
            by_type=by_type,
            by_level=by_level,
        )

    def create_slo_policy(
        self,
        tenant_id: str,
        actor_id: str,
        payload: ObservabilitySloPolicyCreate,
    ) -> ObservabilitySloPolicy:
        policy_key = self._normalize_non_empty(payload.policy_key, "policy_key")
        service_name = self._normalize_non_empty(payload.service_name, "service_name")
        signal_name = self._normalize_non_empty(payload.signal_name, "signal_name")
        with self._session() as session:
            row = ObservabilitySloPolicy(
                tenant_id=tenant_id,
                policy_key=policy_key,
                service_name=service_name,
                signal_name=signal_name,
                target_ratio=payload.target_ratio,
                latency_threshold_ms=payload.latency_threshold_ms,
                window_minutes=payload.window_minutes,
                minimum_samples=payload.minimum_samples,
                alert_severity=payload.alert_severity,
                is_active=payload.is_active,
                detail=payload.detail,
                created_by=actor_id,
            )
            session.add(row)
            try:
                session.commit()
            except IntegrityError as exc:
                session.rollback()
                raise ConflictError("slo policy key already exists in tenant") from exc
            session.refresh(row)
            return row

    def list_slo_policies(
        self,
        tenant_id: str,
        *,
        is_active: bool | None = None,
    ) -> list[ObservabilitySloPolicy]:
        with self._session() as session:
            statement = select(ObservabilitySloPolicy).where(ObservabilitySloPolicy.tenant_id == tenant_id)
            if is_active is not None:
                statement = statement.where(ObservabilitySloPolicy.is_active == is_active)
            rows = list(session.exec(statement).all())
        return sorted(rows, key=lambda item: item.created_at, reverse=True)

    def _resolve_oncall_target(
        self,
        session: Session,
        tenant_id: str,
        at_time: datetime,
    ) -> str | None:
        from app.domain.models import AlertOncallShift

        now = self._as_utc(at_time)
        rows = list(
            session.exec(
                select(AlertOncallShift)
                .where(AlertOncallShift.tenant_id == tenant_id)
                .where(col(AlertOncallShift.is_active).is_(True))
                .where(AlertOncallShift.starts_at <= now)
                .where(AlertOncallShift.ends_at > now)
            ).all()
        )
        if not rows:
            return None
        best = sorted(rows, key=lambda item: item.starts_at, reverse=True)[0]
        return best.target

    def evaluate_slo_policies(
        self,
        tenant_id: str,
        actor_id: str,
        payload: ObservabilitySloEvaluateRequest,
    ) -> tuple[list[ObservabilitySloEvaluation], int]:
        with self._session() as session:
            policy_statement = select(ObservabilitySloPolicy).where(ObservabilitySloPolicy.tenant_id == tenant_id)
            policy_statement = policy_statement.where(col(ObservabilitySloPolicy.is_active).is_(True))
            if payload.policy_ids:
                policy_statement = policy_statement.where(col(ObservabilitySloPolicy.id).in_(payload.policy_ids))
            policies = list(session.exec(policy_statement).all())
            if not policies:
                raise NotFoundError("slo policy not found")

            created: list[ObservabilitySloEvaluation] = []
            alerts_created = 0
            now = now_utc()
            for policy in policies:
                window_minutes = payload.window_minutes or policy.window_minutes
                window_start = now - timedelta(minutes=window_minutes)
                signal_rows = list(
                    session.exec(
                        select(ObservabilitySignal)
                        .where(ObservabilitySignal.tenant_id == tenant_id)
                        .where(ObservabilitySignal.service_name == policy.service_name)
                        .where(ObservabilitySignal.signal_name == policy.signal_name)
                        .where(ObservabilitySignal.created_at >= window_start)
                        .where(ObservabilitySignal.created_at <= now)
                    ).all()
                )
                total_samples = len(signal_rows)
                latency_values = [
                    item.duration_ms for item in signal_rows if item.duration_ms is not None and item.duration_ms >= 0
                ]
                bad_count = 0
                for signal_row in signal_rows:
                    is_error = signal_row.level == ObservabilitySignalLevel.ERROR
                    if signal_row.status_code is not None and signal_row.status_code >= 500:
                        is_error = True
                    if (
                        policy.latency_threshold_ms is not None
                        and signal_row.duration_ms is not None
                        and signal_row.duration_ms > policy.latency_threshold_ms
                    ):
                        is_error = True
                    if is_error:
                        bad_count += 1
                good_samples = max(0, total_samples - bad_count)
                availability_ratio = 1.0 if total_samples == 0 else good_samples / total_samples
                error_ratio = 1.0 - availability_ratio
                p95_latency = self._p95(latency_values)
                insufficient_samples = total_samples < policy.minimum_samples
                breached = (not insufficient_samples) and (availability_ratio < policy.target_ratio)

                evaluation = ObservabilitySloEvaluation(
                    tenant_id=tenant_id,
                    policy_id=policy.id,
                    window_start=window_start,
                    window_end=now,
                    total_samples=total_samples,
                    good_samples=good_samples,
                    availability_ratio=availability_ratio,
                    error_ratio=error_ratio,
                    p95_latency_ms=p95_latency,
                    status=ObservabilitySloStatus.BREACHED if breached else ObservabilitySloStatus.HEALTHY,
                    alert_triggered=False,
                    alert_event_id=None,
                    oncall_target=None,
                    detail={
                        "policy_key": policy.policy_key,
                        "minimum_samples": policy.minimum_samples,
                        "insufficient_samples": insufficient_samples,
                        "evaluated_by": actor_id,
                    },
                )
                session.add(evaluation)
                session.flush()

                if breached and not payload.dry_run:
                    oncall_target = self._resolve_oncall_target(session, tenant_id, now)
                    alert = ObservabilityAlertEvent(
                        tenant_id=tenant_id,
                        source="SLO",
                        severity=policy.alert_severity,
                        status=ObservabilityAlertStatus.OPEN,
                        title=f"SLO breached: {policy.policy_key}",
                        message=(
                            f"service={policy.service_name} signal={policy.signal_name} "
                            f"availability={availability_ratio:.4f} target={policy.target_ratio:.4f}"
                        ),
                        policy_id=policy.id,
                        target=oncall_target,
                        detail={
                            "evaluation_id": evaluation.id,
                            "window_minutes": window_minutes,
                            "error_ratio": round(error_ratio, 6),
                            "p95_latency_ms": p95_latency,
                        },
                    )
                    session.add(alert)
                    session.flush()
                    evaluation.alert_triggered = True
                    evaluation.alert_event_id = alert.id
                    evaluation.oncall_target = oncall_target
                    session.add(evaluation)
                    alerts_created += 1

                created.append(evaluation)
            session.commit()
            for eval_row in created:
                session.refresh(eval_row)
            return created, alerts_created

    def list_slo_evaluations(
        self,
        tenant_id: str,
        *,
        status: ObservabilitySloStatus | None = None,
        limit: int = 100,
    ) -> list[ObservabilitySloEvaluation]:
        scoped_limit = min(max(limit, 1), 1000)
        with self._session() as session:
            statement = select(ObservabilitySloEvaluation).where(
                ObservabilitySloEvaluation.tenant_id == tenant_id
            )
            if status is not None:
                statement = statement.where(ObservabilitySloEvaluation.status == status)
            rows = list(session.exec(statement).all())
        rows_sorted = sorted(rows, key=lambda item: item.created_at, reverse=True)
        return rows_sorted[:scoped_limit]

    def get_slo_overview(self, tenant_id: str) -> ObservabilitySloOverviewRead:
        rows = self.list_slo_evaluations(tenant_id, limit=50)
        healthy = len([item for item in rows if item.status == ObservabilitySloStatus.HEALTHY])
        breached = len([item for item in rows if item.status == ObservabilitySloStatus.BREACHED])
        policies = self.list_slo_policies(tenant_id)
        latest = rows[0].created_at if rows else None
        return ObservabilitySloOverviewRead(
            policy_count=len(policies),
            healthy_count=healthy,
            breached_count=breached,
            latest_evaluated_at=latest,
            items=[ObservabilitySloEvaluationRead.model_validate(item) for item in rows],
        )

    def list_alert_events(
        self,
        tenant_id: str,
        *,
        status: ObservabilityAlertStatus | None = None,
        source: str | None = None,
        limit: int = 100,
    ) -> list[ObservabilityAlertEvent]:
        scoped_limit = min(max(limit, 1), 1000)
        with self._session() as session:
            statement = select(ObservabilityAlertEvent).where(ObservabilityAlertEvent.tenant_id == tenant_id)
            if status is not None:
                statement = statement.where(ObservabilityAlertEvent.status == status)
            if source is not None:
                statement = statement.where(ObservabilityAlertEvent.source == source.strip())
            rows = list(session.exec(statement).all())
        rows_sorted = sorted(rows, key=lambda item: item.created_at, reverse=True)
        return rows_sorted[:scoped_limit]

    def run_backup(
        self,
        tenant_id: str,
        actor_id: str,
        payload: ReliabilityBackupRunRequest,
    ) -> ReliabilityBackupRun:
        with self._session() as session:
            signal_count = session.exec(
                select(ObservabilitySignal.id).where(ObservabilitySignal.tenant_id == tenant_id)
            ).all()
            policy_count = session.exec(
                select(ObservabilitySloPolicy.id).where(ObservabilitySloPolicy.tenant_id == tenant_id)
            ).all()
            alert_count = session.exec(
                select(ObservabilityAlertEvent.id).where(ObservabilityAlertEvent.tenant_id == tenant_id)
            ).all()
            snapshot = {
                "signals": len(signal_count),
                "slo_policies": len(policy_count),
                "observability_alerts": len(alert_count),
                "generated_at": now_utc().isoformat(),
            }
            checksum = hashlib.sha256(
                json.dumps(snapshot, sort_keys=True, ensure_ascii=True).encode("utf-8")
            ).hexdigest()
            now = now_utc()
            row = ReliabilityBackupRun(
                tenant_id=tenant_id,
                run_type=payload.run_type,
                status=ReliabilityBackupRunStatus.SUCCESS,
                storage_uri=payload.storage_uri,
                checksum=checksum,
                is_drill=payload.is_drill,
                detail={"snapshot": snapshot, **payload.detail},
                triggered_by=actor_id,
                created_at=now,
                completed_at=now,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return row

    def list_backups(self, tenant_id: str, *, limit: int = 100) -> list[ReliabilityBackupRun]:
        scoped_limit = min(max(limit, 1), 1000)
        with self._session() as session:
            rows = list(
                session.exec(
                    select(ReliabilityBackupRun).where(ReliabilityBackupRun.tenant_id == tenant_id)
                ).all()
            )
        rows_sorted = sorted(rows, key=lambda item: item.created_at, reverse=True)
        return rows_sorted[:scoped_limit]

    def run_restore_drill(
        self,
        tenant_id: str,
        backup_run_id: str,
        actor_id: str,
        payload: ReliabilityRestoreDrillRequest,
    ) -> ReliabilityRestoreDrill:
        with self._session() as session:
            backup = session.exec(
                select(ReliabilityBackupRun)
                .where(ReliabilityBackupRun.tenant_id == tenant_id)
                .where(ReliabilityBackupRun.id == backup_run_id)
            ).first()
            if backup is None:
                raise NotFoundError("backup run not found")
            status = (
                ReliabilityRestoreDrillStatus.PASSED
                if payload.simulated_restore_seconds <= payload.objective_rto_seconds
                else ReliabilityRestoreDrillStatus.FAILED
            )
            row = ReliabilityRestoreDrill(
                tenant_id=tenant_id,
                backup_run_id=backup.id,
                status=status,
                objective_rto_seconds=payload.objective_rto_seconds,
                actual_rto_seconds=payload.simulated_restore_seconds,
                detail=payload.detail,
                executed_by=actor_id,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return row

    def list_restore_drills(self, tenant_id: str, *, limit: int = 100) -> list[ReliabilityRestoreDrill]:
        scoped_limit = min(max(limit, 1), 1000)
        with self._session() as session:
            rows = list(
                session.exec(
                    select(ReliabilityRestoreDrill).where(ReliabilityRestoreDrill.tenant_id == tenant_id)
                ).all()
            )
        rows_sorted = sorted(rows, key=lambda item: item.created_at, reverse=True)
        return rows_sorted[:scoped_limit]

    def run_security_inspection(
        self,
        tenant_id: str,
        actor_id: str,
        payload: SecurityInspectionRunRequest,
    ) -> tuple[SecurityInspectionRun, list[SecurityInspectionItem]]:
        with self._session() as session:
            checks: list[tuple[str, SecurityInspectionCheckStatus, str, dict[str, Any]]] = []
            active_users = list(
                session.exec(
                    select(User).where(User.tenant_id == tenant_id).where(col(User.is_active).is_(True))
                ).all()
            )
            if active_users:
                checks.append(
                    (
                        "identity.active_users",
                        SecurityInspectionCheckStatus.PASS,
                        "tenant has active users",
                        {"active_users": len(active_users)},
                    )
                )
            else:
                checks.append(
                    (
                        "identity.active_users",
                        SecurityInspectionCheckStatus.FAIL,
                        "tenant has no active user",
                        {"active_users": 0},
                    )
                )

            recent_backups = list(
                session.exec(
                    select(ReliabilityBackupRun)
                    .where(ReliabilityBackupRun.tenant_id == tenant_id)
                    .where(ReliabilityBackupRun.status == ReliabilityBackupRunStatus.SUCCESS)
                ).all()
            )
            latest_backup = sorted(recent_backups, key=lambda item: item.created_at, reverse=True)[0] if recent_backups else None
            if latest_backup is None:
                checks.append(
                    (
                        "reliability.backup_recency",
                        SecurityInspectionCheckStatus.FAIL,
                        "no successful backup run found",
                        {},
                    )
                )
            elif self._as_utc(latest_backup.created_at) >= self._as_utc(now_utc() - timedelta(days=7)):
                checks.append(
                    (
                        "reliability.backup_recency",
                        SecurityInspectionCheckStatus.PASS,
                        "latest backup is within 7 days",
                        {"backup_run_id": latest_backup.id},
                    )
                )
            else:
                checks.append(
                    (
                        "reliability.backup_recency",
                        SecurityInspectionCheckStatus.WARN,
                        "latest backup is older than 7 days",
                        {"backup_run_id": latest_backup.id},
                    )
                )

            open_alerts = list(
                session.exec(
                    select(ObservabilityAlertEvent)
                    .where(ObservabilityAlertEvent.tenant_id == tenant_id)
                    .where(ObservabilityAlertEvent.status == ObservabilityAlertStatus.OPEN)
                ).all()
            )
            if len(open_alerts) <= 3:
                checks.append(
                    (
                        "observability.open_alert_budget",
                        SecurityInspectionCheckStatus.PASS,
                        "open observability alerts are within budget",
                        {"open_alerts": len(open_alerts)},
                    )
                )
            else:
                checks.append(
                    (
                        "observability.open_alert_budget",
                        SecurityInspectionCheckStatus.WARN,
                        "open observability alerts exceed budget",
                        {"open_alerts": len(open_alerts)},
                    )
                )

            from app.domain.models import AlertOncallShift

            now = now_utc()
            active_shifts = list(
                session.exec(
                    select(AlertOncallShift)
                    .where(AlertOncallShift.tenant_id == tenant_id)
                    .where(col(AlertOncallShift.is_active).is_(True))
                    .where(AlertOncallShift.starts_at <= now)
                    .where(AlertOncallShift.ends_at > now)
                ).all()
            )
            if active_shifts:
                checks.append(
                    (
                        "alert.oncall_coverage",
                        SecurityInspectionCheckStatus.PASS,
                        "active oncall shift exists",
                        {"active_shifts": len(active_shifts)},
                    )
                )
            else:
                checks.append(
                    (
                        "alert.oncall_coverage",
                        SecurityInspectionCheckStatus.WARN,
                        "no active oncall shift found",
                        {},
                    )
                )

            recent_slo = list(
                session.exec(
                    select(ObservabilitySloEvaluation)
                    .where(ObservabilitySloEvaluation.tenant_id == tenant_id)
                    .where(ObservabilitySloEvaluation.created_at >= now - timedelta(days=1))
                ).all()
            )
            if recent_slo:
                checks.append(
                    (
                        "observability.slo_recent_eval",
                        SecurityInspectionCheckStatus.PASS,
                        "slo has recent evaluations",
                        {"recent_evaluations": len(recent_slo)},
                    )
                )
            else:
                checks.append(
                    (
                        "observability.slo_recent_eval",
                        SecurityInspectionCheckStatus.WARN,
                        "no slo evaluation in last 24h",
                        {},
                    )
                )

            passed = len([item for item in checks if item[1] == SecurityInspectionCheckStatus.PASS])
            warned = len([item for item in checks if item[1] == SecurityInspectionCheckStatus.WARN])
            failed = len([item for item in checks if item[1] == SecurityInspectionCheckStatus.FAIL])
            total = len(checks)
            raw_score = (passed + 0.5 * warned) / total if total > 0 else 1.0
            score_percent = round(raw_score * 100.0, 2)

            run = SecurityInspectionRun(
                tenant_id=tenant_id,
                baseline_version=payload.baseline_version.strip() or "phase25-v1",
                total_checks=total,
                passed_checks=passed,
                warned_checks=warned,
                failed_checks=failed,
                score_percent=score_percent,
                detail=payload.detail,
                executed_by=actor_id,
            )
            session.add(run)
            session.flush()

            items: list[SecurityInspectionItem] = []
            for check_key, status, message, detail in checks:
                row = SecurityInspectionItem(
                    tenant_id=tenant_id,
                    run_id=run.id,
                    check_key=check_key,
                    status=status,
                    message=message,
                    detail=detail,
                )
                session.add(row)
                items.append(row)

            if failed > 0:
                oncall_target = self._resolve_oncall_target(session, tenant_id, now)
                session.add(
                    ObservabilityAlertEvent(
                        tenant_id=tenant_id,
                        source="SECURITY",
                        severity=ObservabilityAlertSeverity.P1,
                        status=ObservabilityAlertStatus.OPEN,
                        title="Security baseline inspection failed",
                        message=f"failed_checks={failed} total_checks={total}",
                        policy_id=None,
                        target=oncall_target,
                        detail={"inspection_run_id": run.id, "score_percent": score_percent},
                    )
                )

            session.commit()
            session.refresh(run)
            for item in items:
                session.refresh(item)
            return run, items

    def list_security_inspections(self, tenant_id: str, *, limit: int = 50) -> list[tuple[SecurityInspectionRun, list[SecurityInspectionItem]]]:
        scoped_limit = min(max(limit, 1), 200)
        with self._session() as session:
            runs = list(
                session.exec(
                    select(SecurityInspectionRun).where(SecurityInspectionRun.tenant_id == tenant_id)
                ).all()
            )
            runs_sorted = sorted(runs, key=lambda item: item.created_at, reverse=True)[:scoped_limit]
            if not runs_sorted:
                return []
            run_ids = [item.id for item in runs_sorted]
            all_items = list(
                session.exec(
                    select(SecurityInspectionItem)
                    .where(SecurityInspectionItem.tenant_id == tenant_id)
                    .where(col(SecurityInspectionItem.run_id).in_(run_ids))
                ).all()
            )
            by_run: dict[str, list[SecurityInspectionItem]] = {}
            for item in all_items:
                by_run.setdefault(item.run_id, []).append(item)
            result: list[tuple[SecurityInspectionRun, list[SecurityInspectionItem]]] = []
            for run in runs_sorted:
                run_items = sorted(by_run.get(run.id, []), key=lambda item: item.check_key)
                result.append((run, run_items))
            return result

    def upsert_capacity_policy(
        self,
        tenant_id: str,
        meter_key: str,
        actor_id: str,
        payload: CapacityPolicyUpsertRequest,
    ) -> CapacityPolicy:
        normalized_meter = self._normalize_non_empty(meter_key, "meter_key")
        if payload.min_replicas > payload.max_replicas:
            raise ConflictError("min_replicas must be less than or equal to max_replicas")
        if not (payload.min_replicas <= payload.current_replicas <= payload.max_replicas):
            raise ConflictError("current_replicas must be within [min_replicas, max_replicas]")
        if payload.scale_in_threshold_pct >= payload.scale_out_threshold_pct:
            raise ConflictError("scale_in_threshold_pct must be less than scale_out_threshold_pct")

        with self._session() as session:
            existing = session.exec(
                select(CapacityPolicy)
                .where(CapacityPolicy.tenant_id == tenant_id)
                .where(CapacityPolicy.meter_key == normalized_meter)
            ).first()
            now = now_utc()
            if existing is None:
                row = CapacityPolicy(
                    tenant_id=tenant_id,
                    meter_key=normalized_meter,
                    target_utilization_pct=payload.target_utilization_pct,
                    scale_out_threshold_pct=payload.scale_out_threshold_pct,
                    scale_in_threshold_pct=payload.scale_in_threshold_pct,
                    min_replicas=payload.min_replicas,
                    max_replicas=payload.max_replicas,
                    current_replicas=payload.current_replicas,
                    is_active=payload.is_active,
                    detail=payload.detail,
                    updated_by=actor_id,
                    created_at=now,
                    updated_at=now,
                )
                session.add(row)
            else:
                row = existing
                row.target_utilization_pct = payload.target_utilization_pct
                row.scale_out_threshold_pct = payload.scale_out_threshold_pct
                row.scale_in_threshold_pct = payload.scale_in_threshold_pct
                row.min_replicas = payload.min_replicas
                row.max_replicas = payload.max_replicas
                row.current_replicas = payload.current_replicas
                row.is_active = payload.is_active
                row.detail = payload.detail
                row.updated_by = actor_id
                row.updated_at = now
                session.add(row)
            try:
                session.commit()
            except IntegrityError as exc:
                session.rollback()
                raise ConflictError("failed to upsert capacity policy") from exc
            session.refresh(row)
            return row

    def list_capacity_policies(self, tenant_id: str) -> list[CapacityPolicy]:
        with self._session() as session:
            rows = list(session.exec(select(CapacityPolicy).where(CapacityPolicy.tenant_id == tenant_id)).all())
        return sorted(rows, key=lambda item: item.meter_key)

    def _get_capacity_policy(self, session: Session, tenant_id: str, meter_key: str) -> CapacityPolicy:
        row = session.exec(
            select(CapacityPolicy)
            .where(CapacityPolicy.tenant_id == tenant_id)
            .where(CapacityPolicy.meter_key == meter_key)
            .where(col(CapacityPolicy.is_active).is_(True))
        ).first()
        if row is None:
            raise NotFoundError("capacity policy not found")
        return row

    def forecast_capacity(
        self,
        tenant_id: str,
        payload: CapacityForecastRequest,
    ) -> CapacityForecast:
        meter_key = self._normalize_non_empty(payload.meter_key, "meter_key")
        with self._session() as session:
            policy = self._get_capacity_policy(session, tenant_id, meter_key)
            now = now_utc()
            sample_start = now - timedelta(minutes=payload.sample_minutes)
            signal_rows = list(
                session.exec(
                    select(ObservabilitySignal)
                    .where(ObservabilitySignal.tenant_id == tenant_id)
                    .where(ObservabilitySignal.signal_type == ObservabilitySignalType.METRIC)
                    .where(ObservabilitySignal.signal_name == meter_key)
                    .where(ObservabilitySignal.created_at >= sample_start)
                    .where(ObservabilitySignal.created_at <= now)
                ).all()
            )
            numeric_values = [item.numeric_value for item in signal_rows if item.numeric_value is not None]
            predicted_usage = round(sum(numeric_values) / len(numeric_values), 4) if numeric_values else 0.0

            if predicted_usage >= float(policy.scale_out_threshold_pct):
                decision = CapacityDecision.SCALE_OUT
                recommended_replicas = min(policy.max_replicas, policy.current_replicas + 1)
            elif predicted_usage <= float(policy.scale_in_threshold_pct):
                decision = CapacityDecision.SCALE_IN
                recommended_replicas = max(policy.min_replicas, policy.current_replicas - 1)
            else:
                decision = CapacityDecision.HOLD
                recommended_replicas = policy.current_replicas

            row = CapacityForecast(
                tenant_id=tenant_id,
                policy_id=policy.id,
                meter_key=meter_key,
                window_start=now,
                window_end=now + timedelta(minutes=payload.window_minutes),
                predicted_usage=predicted_usage,
                recommended_replicas=recommended_replicas,
                decision=decision,
                detail={
                    "sample_minutes": payload.sample_minutes,
                    "sample_count": len(numeric_values),
                    "current_replicas": policy.current_replicas,
                },
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return row

    def list_capacity_forecasts(self, tenant_id: str, *, meter_key: str | None = None, limit: int = 100) -> list[CapacityForecast]:
        scoped_limit = min(max(limit, 1), 1000)
        with self._session() as session:
            statement = select(CapacityForecast).where(CapacityForecast.tenant_id == tenant_id)
            if meter_key is not None:
                statement = statement.where(CapacityForecast.meter_key == meter_key.strip())
            rows = list(session.exec(statement).all())
        rows_sorted = sorted(rows, key=lambda item: item.generated_at, reverse=True)
        return rows_sorted[:scoped_limit]
