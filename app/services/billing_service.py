from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, select

from app.domain.models import (
    BillingEffectiveQuotaRead,
    BillingInvoice,
    BillingInvoiceCloseRequest,
    BillingInvoiceGenerateRequest,
    BillingInvoiceLine,
    BillingInvoiceStatus,
    BillingInvoiceVoidRequest,
    BillingPlanCatalog,
    BillingPlanCreate,
    BillingPlanQuota,
    BillingQuotaCheckRead,
    BillingQuotaCheckRequest,
    BillingQuotaOverrideUpsertRequest,
    BillingSubscriptionCreate,
    BillingSubscriptionStatus,
    BillingTenantQuotaSnapshotRead,
    BillingUsageAggregateDaily,
    BillingUsageEvent,
    BillingUsageIngestRequest,
    BillingUsageSummaryRead,
    TenantQuotaOverride,
    TenantSubscription,
)
from app.infra.db import get_engine


class BillingError(Exception):
    pass


class NotFoundError(BillingError):
    pass


class ConflictError(BillingError):
    pass


class BillingService:
    def _session(self) -> Session:
        return Session(get_engine(), expire_on_commit=False)

    def _get_scoped_plan(self, session: Session, tenant_id: str, plan_id: str) -> BillingPlanCatalog:
        row = session.exec(
            select(BillingPlanCatalog)
            .where(BillingPlanCatalog.tenant_id == tenant_id)
            .where(BillingPlanCatalog.id == plan_id)
        ).first()
        if row is None:
            raise NotFoundError("billing plan not found")
        return row

    def _get_scoped_invoice(self, session: Session, tenant_id: str, invoice_id: str) -> BillingInvoice:
        row = session.exec(
            select(BillingInvoice)
            .where(BillingInvoice.tenant_id == tenant_id)
            .where(BillingInvoice.id == invoice_id)
        ).first()
        if row is None:
            raise NotFoundError("billing invoice not found")
        return row

    def _get_active_subscription(self, session: Session, tenant_id: str) -> TenantSubscription:
        row = session.exec(
            select(TenantSubscription)
            .where(TenantSubscription.tenant_id == tenant_id)
            .where(TenantSubscription.status == BillingSubscriptionStatus.ACTIVE)
            .order_by(col(TenantSubscription.start_at).desc())
        ).first()
        if row is None:
            raise ConflictError("active subscription not found")
        return row

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

    @classmethod
    def _day_bucket(cls, value: datetime) -> datetime:
        normalized = cls._as_utc(value)
        return datetime(
            normalized.year,
            normalized.month,
            normalized.day,
            tzinfo=UTC,
        )

    @classmethod
    def _month_window(cls, value: datetime) -> tuple[datetime, datetime]:
        normalized = cls._as_utc(value)
        month_start = datetime(normalized.year, normalized.month, 1, tzinfo=UTC)
        if normalized.month == 12:
            next_month_start = datetime(normalized.year + 1, 1, 1, tzinfo=UTC)
        else:
            next_month_start = datetime(normalized.year, normalized.month + 1, 1, tzinfo=UTC)
        return month_start, next_month_start

    @staticmethod
    def _validate_quota_keys(items: list[dict[str, Any]], field_name: str) -> None:
        keys: set[str] = set()
        for item in items:
            key_raw = item.get("quota_key")
            if not isinstance(key_raw, str):
                raise ConflictError(f"{field_name}.quota_key must be string")
            key = key_raw.strip()
            if not key:
                raise ConflictError(f"{field_name}.quota_key cannot be empty")
            if key in keys:
                raise ConflictError(f"{field_name}.quota_key cannot duplicate")
            keys.add(key)

    def create_plan(
        self,
        tenant_id: str,
        actor_id: str,
        payload: BillingPlanCreate,
    ) -> tuple[BillingPlanCatalog, list[BillingPlanQuota]]:
        self._validate_quota_keys(
            [item.model_dump(mode="python") for item in payload.quotas],
            "quotas",
        )
        plan_code = self._normalize_non_empty(payload.plan_code, "plan_code")
        display_name = self._normalize_non_empty(payload.display_name, "display_name")
        currency = self._normalize_non_empty(payload.currency, "currency").upper()

        with self._session() as session:
            plan = BillingPlanCatalog(
                tenant_id=tenant_id,
                plan_code=plan_code,
                display_name=display_name,
                description=payload.description,
                billing_cycle=payload.billing_cycle,
                price_cents=payload.price_cents,
                currency=currency,
                is_active=payload.is_active,
                created_by=actor_id,
            )
            session.add(plan)
            session.flush()

            quotas: list[BillingPlanQuota] = []
            now = datetime.now(UTC)
            for item in payload.quotas:
                quota = BillingPlanQuota(
                    tenant_id=tenant_id,
                    plan_id=plan.id,
                    quota_key=item.quota_key.strip(),
                    quota_limit=item.quota_limit,
                    enforcement_mode=item.enforcement_mode,
                    detail=item.detail,
                    created_at=now,
                    updated_at=now,
                )
                quotas.append(quota)
                session.add(quota)

            try:
                session.commit()
            except IntegrityError as exc:
                session.rollback()
                raise ConflictError("billing plan already exists or quota key conflicts") from exc

            session.refresh(plan)
            for quota in quotas:
                session.refresh(quota)
            return plan, quotas

    def list_plans(
        self,
        tenant_id: str,
        *,
        plan_code: str | None = None,
        is_active: bool | None = None,
    ) -> list[tuple[BillingPlanCatalog, list[BillingPlanQuota]]]:
        with self._session() as session:
            statement = select(BillingPlanCatalog).where(BillingPlanCatalog.tenant_id == tenant_id)
            if plan_code is not None:
                statement = statement.where(BillingPlanCatalog.plan_code == plan_code.strip())
            if is_active is not None:
                statement = statement.where(BillingPlanCatalog.is_active == is_active)
            plans = sorted(
                list(session.exec(statement).all()),
                key=lambda item: item.created_at,
                reverse=True,
            )

            if not plans:
                return []
            plan_ids = [item.id for item in plans]
            quota_rows = list(
                session.exec(
                    select(BillingPlanQuota)
                    .where(BillingPlanQuota.tenant_id == tenant_id)
                    .where(col(BillingPlanQuota.plan_id).in_(plan_ids))
                ).all()
            )
            quota_by_plan: dict[str, list[BillingPlanQuota]] = {}
            for row in quota_rows:
                quota_by_plan.setdefault(row.plan_id, []).append(row)
            for key, rows in quota_by_plan.items():
                quota_by_plan[key] = sorted(rows, key=lambda item: item.quota_key)

            return [(plan, quota_by_plan.get(plan.id, [])) for plan in plans]

    def create_subscription(
        self,
        tenant_id: str,
        actor_id: str,
        payload: BillingSubscriptionCreate,
    ) -> TenantSubscription:
        if payload.end_at is not None and payload.end_at <= payload.start_at:
            raise ConflictError("end_at must be later than start_at")

        with self._session() as session:
            _ = self._get_scoped_plan(session, tenant_id, payload.plan_id)

            if payload.status == BillingSubscriptionStatus.ACTIVE:
                active_exists = session.exec(
                    select(TenantSubscription.id)
                    .where(TenantSubscription.tenant_id == tenant_id)
                    .where(TenantSubscription.status == BillingSubscriptionStatus.ACTIVE)
                    .where(
                        or_(
                            col(TenantSubscription.end_at).is_(None),
                            col(TenantSubscription.end_at) >= payload.start_at,
                        )
                    )
                ).first()
                if active_exists is not None:
                    raise ConflictError("active subscription already exists for tenant")

            row = TenantSubscription(
                tenant_id=tenant_id,
                plan_id=payload.plan_id,
                status=payload.status,
                start_at=payload.start_at,
                end_at=payload.end_at,
                auto_renew=payload.auto_renew,
                detail=payload.detail,
                created_by=actor_id,
            )
            session.add(row)
            try:
                session.commit()
            except IntegrityError as exc:
                session.rollback()
                raise ConflictError("failed to create tenant subscription") from exc
            session.refresh(row)
            return row

    def list_subscriptions(self, tenant_id: str) -> list[TenantSubscription]:
        with self._session() as session:
            rows = list(
                session.exec(
                    select(TenantSubscription).where(TenantSubscription.tenant_id == tenant_id)
                ).all()
            )
            return sorted(rows, key=lambda item: item.start_at, reverse=True)

    def upsert_quota_overrides(
        self,
        tenant_id: str,
        actor_id: str,
        payload: BillingQuotaOverrideUpsertRequest,
    ) -> list[TenantQuotaOverride]:
        self._validate_quota_keys(
            [item.model_dump(mode="python") for item in payload.overrides],
            "overrides",
        )
        with self._session() as session:
            now = datetime.now(UTC)
            existing = {
                row.quota_key: row
                for row in session.exec(
                    select(TenantQuotaOverride).where(TenantQuotaOverride.tenant_id == tenant_id)
                ).all()
            }
            for item in payload.overrides:
                key = item.quota_key.strip()
                row = existing.get(key)
                if row is None:
                    row = TenantQuotaOverride(
                        tenant_id=tenant_id,
                        quota_key=key,
                        override_limit=item.override_limit,
                        enforcement_mode=item.enforcement_mode,
                        reason=item.reason,
                        is_active=item.is_active,
                        detail=item.detail,
                        updated_by=actor_id,
                        created_at=now,
                        updated_at=now,
                    )
                    session.add(row)
                    continue

                row.override_limit = item.override_limit
                row.enforcement_mode = item.enforcement_mode
                row.reason = item.reason
                row.is_active = item.is_active
                row.detail = item.detail
                row.updated_by = actor_id
                row.updated_at = now
                session.add(row)

            try:
                session.commit()
            except IntegrityError as exc:
                session.rollback()
                raise ConflictError("failed to upsert tenant quota overrides") from exc

        return self.list_quota_overrides(tenant_id)

    def list_quota_overrides(self, tenant_id: str) -> list[TenantQuotaOverride]:
        with self._session() as session:
            rows = list(
                session.exec(
                    select(TenantQuotaOverride).where(TenantQuotaOverride.tenant_id == tenant_id)
                ).all()
            )
            return sorted(rows, key=lambda item: item.quota_key)

    def get_effective_quotas(self, tenant_id: str) -> BillingTenantQuotaSnapshotRead:
        with self._session() as session:
            active_subscription = session.exec(
                select(TenantSubscription)
                .where(TenantSubscription.tenant_id == tenant_id)
                .where(TenantSubscription.status == BillingSubscriptionStatus.ACTIVE)
                .order_by(col(TenantSubscription.start_at).desc())
            ).first()

            plan_id: str | None = None
            plan_code: str | None = None
            quota_map: dict[str, BillingEffectiveQuotaRead] = {}

            if active_subscription is not None:
                plan = self._get_scoped_plan(session, tenant_id, active_subscription.plan_id)
                plan_id = plan.id
                plan_code = plan.plan_code
                plan_quotas = list(
                    session.exec(
                        select(BillingPlanQuota)
                        .where(BillingPlanQuota.tenant_id == tenant_id)
                        .where(BillingPlanQuota.plan_id == plan.id)
                    ).all()
                )
                for row in plan_quotas:
                    quota_map[row.quota_key] = BillingEffectiveQuotaRead(
                        quota_key=row.quota_key,
                        quota_limit=row.quota_limit,
                        enforcement_mode=row.enforcement_mode,
                        source="PLAN",
                    )

            overrides = list(
                session.exec(
                    select(TenantQuotaOverride)
                    .where(TenantQuotaOverride.tenant_id == tenant_id)
                    .where(col(TenantQuotaOverride.is_active).is_(True))
                ).all()
            )
            for override_row in overrides:
                quota_map[override_row.quota_key] = BillingEffectiveQuotaRead(
                    quota_key=override_row.quota_key,
                    quota_limit=override_row.override_limit,
                    enforcement_mode=override_row.enforcement_mode,
                    source="OVERRIDE",
                )

            quota_values = sorted(quota_map.values(), key=lambda item: item.quota_key)
            return BillingTenantQuotaSnapshotRead(
                tenant_id=tenant_id,
                subscription_id=active_subscription.id if active_subscription is not None else None,
                plan_id=plan_id,
                plan_code=plan_code,
                quotas=quota_values,
            )

    def ingest_usage_event(
        self,
        tenant_id: str,
        actor_id: str,
        payload: BillingUsageIngestRequest,
    ) -> tuple[BillingUsageEvent, bool]:
        meter_key = self._normalize_non_empty(payload.meter_key, "meter_key")
        source_event_id = self._normalize_non_empty(payload.source_event_id, "source_event_id")
        occurred_at = self._as_utc(payload.occurred_at)
        day_bucket = self._day_bucket(occurred_at)

        with self._session() as session:
            existing = session.exec(
                select(BillingUsageEvent)
                .where(BillingUsageEvent.tenant_id == tenant_id)
                .where(BillingUsageEvent.meter_key == meter_key)
                .where(BillingUsageEvent.source_event_id == source_event_id)
            ).first()
            if existing is not None:
                return existing, True

            now = datetime.now(UTC)
            event = BillingUsageEvent(
                tenant_id=tenant_id,
                meter_key=meter_key,
                quantity=payload.quantity,
                occurred_at=occurred_at,
                source_event_id=source_event_id,
                detail=payload.detail,
                created_by=actor_id,
                created_at=now,
            )
            session.add(event)

            aggregate = session.exec(
                select(BillingUsageAggregateDaily)
                .where(BillingUsageAggregateDaily.tenant_id == tenant_id)
                .where(BillingUsageAggregateDaily.meter_key == meter_key)
                .where(BillingUsageAggregateDaily.usage_date == day_bucket)
            ).first()
            if aggregate is None:
                aggregate = BillingUsageAggregateDaily(
                    tenant_id=tenant_id,
                    meter_key=meter_key,
                    usage_date=day_bucket,
                    total_quantity=payload.quantity,
                    updated_at=now,
                )
            else:
                aggregate.total_quantity += payload.quantity
                aggregate.updated_at = now
            session.add(aggregate)

            try:
                session.commit()
            except IntegrityError as exc:
                session.rollback()
                dedup = session.exec(
                    select(BillingUsageEvent)
                    .where(BillingUsageEvent.tenant_id == tenant_id)
                    .where(BillingUsageEvent.meter_key == meter_key)
                    .where(BillingUsageEvent.source_event_id == source_event_id)
                ).first()
                if dedup is None:
                    raise ConflictError("failed to ingest usage event") from exc
                return dedup, True

            session.refresh(event)
            return event, False

    def list_usage_summary(
        self,
        tenant_id: str,
        *,
        meter_key: str | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
    ) -> list[BillingUsageSummaryRead]:
        normalized_meter = meter_key.strip() if meter_key is not None else None
        from_bucket = self._day_bucket(from_date) if from_date is not None else None
        to_bucket = self._day_bucket(to_date) if to_date is not None else None
        if from_bucket is not None and to_bucket is not None and to_bucket < from_bucket:
            raise ConflictError("to_date must be greater than or equal to from_date")

        with self._session() as session:
            statement = select(BillingUsageAggregateDaily).where(
                BillingUsageAggregateDaily.tenant_id == tenant_id
            )
            if normalized_meter:
                statement = statement.where(BillingUsageAggregateDaily.meter_key == normalized_meter)
            if from_bucket is not None:
                statement = statement.where(BillingUsageAggregateDaily.usage_date >= from_bucket)
            if to_bucket is not None:
                statement = statement.where(BillingUsageAggregateDaily.usage_date <= to_bucket)
            rows = list(session.exec(statement).all())

        summary: dict[str, int] = {}
        for row in rows:
            summary[row.meter_key] = summary.get(row.meter_key, 0) + row.total_quantity
        result = [
            BillingUsageSummaryRead(
                meter_key=key,
                total_quantity=value,
                from_date=from_bucket,
                to_date=to_bucket,
            )
            for key, value in summary.items()
        ]
        return sorted(result, key=lambda item: item.meter_key)

    def check_quota(
        self,
        tenant_id: str,
        payload: BillingQuotaCheckRequest,
    ) -> BillingQuotaCheckRead:
        meter_key = self._normalize_non_empty(payload.meter_key, "meter_key")
        month_start, next_month_start = self._month_window(payload.as_of)

        with self._session() as session:
            rows = list(
                session.exec(
                    select(BillingUsageAggregateDaily)
                    .where(BillingUsageAggregateDaily.tenant_id == tenant_id)
                    .where(BillingUsageAggregateDaily.meter_key == meter_key)
                    .where(BillingUsageAggregateDaily.usage_date >= month_start)
                    .where(BillingUsageAggregateDaily.usage_date < next_month_start)
                ).all()
            )
            used_quantity = sum(item.total_quantity for item in rows)

        snapshot = self.get_effective_quotas(tenant_id)
        quota = next((item for item in snapshot.quotas if item.quota_key == meter_key), None)
        projected = used_quantity + payload.quantity

        if quota is None:
            return BillingQuotaCheckRead(
                meter_key=meter_key,
                quota_limit=None,
                enforcement_mode=None,
                used_quantity=used_quantity,
                request_quantity=payload.quantity,
                projected_quantity=projected,
                allowed=True,
                source="NO_RULE",
                reason="quota_not_configured",
            )

        if projected <= quota.quota_limit:
            return BillingQuotaCheckRead(
                meter_key=meter_key,
                quota_limit=quota.quota_limit,
                enforcement_mode=quota.enforcement_mode,
                used_quantity=used_quantity,
                request_quantity=payload.quantity,
                projected_quantity=projected,
                allowed=True,
                source=quota.source,
                reason="within_limit",
            )

        if quota.enforcement_mode.value == "HARD_LIMIT":
            allowed = False
            reason = "hard_limit_exceeded"
        else:
            allowed = True
            reason = "soft_limit_exceeded"
        return BillingQuotaCheckRead(
            meter_key=meter_key,
            quota_limit=quota.quota_limit,
            enforcement_mode=quota.enforcement_mode,
            used_quantity=used_quantity,
            request_quantity=payload.quantity,
            projected_quantity=projected,
            allowed=allowed,
            source=quota.source,
            reason=reason,
        )

    def _collect_usage_by_meter(
        self,
        session: Session,
        *,
        tenant_id: str,
        period_start: datetime,
        period_end: datetime,
    ) -> dict[str, int]:
        start_bucket = self._day_bucket(period_start)
        end_bucket = self._day_bucket(period_end)
        statement = (
            select(BillingUsageAggregateDaily)
            .where(BillingUsageAggregateDaily.tenant_id == tenant_id)
            .where(BillingUsageAggregateDaily.usage_date >= start_bucket)
            .where(BillingUsageAggregateDaily.usage_date < end_bucket)
        )
        rows = list(session.exec(statement).all())
        usage_map: dict[str, int] = {}
        for row in rows:
            usage_map[row.meter_key] = usage_map.get(row.meter_key, 0) + row.total_quantity
        return usage_map

    def generate_invoice(
        self,
        tenant_id: str,
        actor_id: str,
        payload: BillingInvoiceGenerateRequest,
    ) -> BillingInvoice:
        period_start = self._as_utc(payload.period_start)
        period_end = self._as_utc(payload.period_end)
        if period_end <= period_start:
            raise ConflictError("period_end must be later than period_start")

        with self._session() as session:
            subscription = self._get_active_subscription(session, tenant_id)
            plan = self._get_scoped_plan(session, tenant_id, subscription.plan_id)
            existing_invoice = session.exec(
                select(BillingInvoice)
                .where(BillingInvoice.tenant_id == tenant_id)
                .where(BillingInvoice.period_start == period_start)
                .where(BillingInvoice.period_end == period_end)
                .order_by(col(BillingInvoice.created_at).desc())
            ).first()

            if existing_invoice is not None and existing_invoice.status == BillingInvoiceStatus.CLOSED:
                raise ConflictError("closed invoice cannot be recomputed")
            if existing_invoice is not None and existing_invoice.status == BillingInvoiceStatus.ISSUED:
                raise ConflictError("issued invoice cannot be recomputed")

            if (
                existing_invoice is not None
                and existing_invoice.status == BillingInvoiceStatus.DRAFT
                and not payload.force_recompute
            ):
                return existing_invoice

            now = datetime.now(UTC)
            if existing_invoice is None:
                invoice = BillingInvoice(
                    tenant_id=tenant_id,
                    subscription_id=subscription.id,
                    plan_id=plan.id,
                    period_start=period_start,
                    period_end=period_end,
                    status=BillingInvoiceStatus.DRAFT,
                    currency=plan.currency,
                    subtotal_cents=0,
                    adjustments_cents=payload.adjustments_cents,
                    total_amount_cents=0,
                    detail=payload.detail,
                    created_by=actor_id,
                    created_at=now,
                    updated_at=now,
                )
                session.add(invoice)
                session.flush()
            else:
                invoice = existing_invoice
                line_rows = list(
                    session.exec(
                        select(BillingInvoiceLine)
                        .where(BillingInvoiceLine.tenant_id == tenant_id)
                        .where(BillingInvoiceLine.invoice_id == invoice.id)
                    ).all()
                )
                for line_row in line_rows:
                    session.delete(line_row)
                invoice.subscription_id = subscription.id
                invoice.plan_id = plan.id
                invoice.currency = plan.currency
                invoice.adjustments_cents = payload.adjustments_cents
                invoice.detail = payload.detail
                invoice.updated_at = now
                session.add(invoice)

            usage_map = self._collect_usage_by_meter(
                session,
                tenant_id=tenant_id,
                period_start=period_start,
                period_end=period_end,
            )
            quotas = list(
                session.exec(
                    select(BillingPlanQuota)
                    .where(BillingPlanQuota.tenant_id == tenant_id)
                    .where(BillingPlanQuota.plan_id == plan.id)
                ).all()
            )
            quota_by_key = {item.quota_key: item for item in quotas}

            lines: list[BillingInvoiceLine] = []
            lines.append(
                BillingInvoiceLine(
                    tenant_id=tenant_id,
                    invoice_id=invoice.id,
                    line_type="PLAN_BASE",
                    meter_key=None,
                    description=f"Plan fee: {plan.display_name}",
                    quantity=1,
                    unit_price_cents=plan.price_cents,
                    amount_cents=plan.price_cents,
                    detail={"plan_code": plan.plan_code},
                    created_at=now,
                )
            )
            for meter_key in sorted(usage_map):
                quantity = usage_map[meter_key]
                if quantity <= 0:
                    continue
                unit_price_cents = 0
                quota_row = quota_by_key.get(meter_key)
                if quota_row is not None:
                    unit_price = quota_row.detail.get("unit_price_cents")
                    if isinstance(unit_price, int) and unit_price >= 0:
                        unit_price_cents = unit_price
                amount_cents = quantity * unit_price_cents
                lines.append(
                    BillingInvoiceLine(
                        tenant_id=tenant_id,
                        invoice_id=invoice.id,
                        line_type="USAGE",
                        meter_key=meter_key,
                        description=f"Usage: {meter_key}",
                        quantity=quantity,
                        unit_price_cents=unit_price_cents,
                        amount_cents=amount_cents,
                        detail={},
                        created_at=now,
                    )
                )
            for line in lines:
                session.add(line)

            subtotal_cents = sum(item.amount_cents for item in lines)
            invoice.subtotal_cents = subtotal_cents
            invoice.total_amount_cents = subtotal_cents + invoice.adjustments_cents
            invoice.status = BillingInvoiceStatus.DRAFT
            invoice.issued_at = None
            invoice.closed_at = None
            invoice.voided_at = None
            invoice.updated_at = now
            session.add(invoice)
            try:
                session.commit()
            except IntegrityError as exc:
                session.rollback()
                raise ConflictError("failed to generate billing invoice") from exc
            session.refresh(invoice)
            return invoice

    def list_invoices(
        self,
        tenant_id: str,
        *,
        period_start: datetime | None = None,
        period_end: datetime | None = None,
        status: BillingInvoiceStatus | None = None,
    ) -> list[BillingInvoice]:
        with self._session() as session:
            statement = select(BillingInvoice).where(BillingInvoice.tenant_id == tenant_id)
            if period_start is not None:
                statement = statement.where(BillingInvoice.period_start >= self._as_utc(period_start))
            if period_end is not None:
                statement = statement.where(BillingInvoice.period_end <= self._as_utc(period_end))
            if status is not None:
                statement = statement.where(BillingInvoice.status == status)
            rows = list(session.exec(statement).all())
            return sorted(rows, key=lambda item: item.period_start, reverse=True)

    def get_invoice_detail(
        self,
        tenant_id: str,
        invoice_id: str,
    ) -> tuple[BillingInvoice, list[BillingInvoiceLine]]:
        with self._session() as session:
            invoice = self._get_scoped_invoice(session, tenant_id, invoice_id)
            lines = list(
                session.exec(
                    select(BillingInvoiceLine)
                    .where(BillingInvoiceLine.tenant_id == tenant_id)
                    .where(BillingInvoiceLine.invoice_id == invoice.id)
                ).all()
            )
            return invoice, sorted(lines, key=lambda item: (item.line_type, item.created_at))

    def close_invoice(
        self,
        tenant_id: str,
        invoice_id: str,
        actor_id: str,
        payload: BillingInvoiceCloseRequest,
    ) -> BillingInvoice:
        with self._session() as session:
            invoice = self._get_scoped_invoice(session, tenant_id, invoice_id)
            if invoice.status == BillingInvoiceStatus.CLOSED:
                raise ConflictError("invoice already closed")
            if invoice.status == BillingInvoiceStatus.VOID:
                raise ConflictError("void invoice cannot be closed")
            now = datetime.now(UTC)
            if invoice.issued_at is None:
                invoice.issued_at = now
            invoice.status = BillingInvoiceStatus.CLOSED
            invoice.closed_at = now
            invoice.updated_at = now
            if payload.note:
                detail = dict(invoice.detail)
                detail["close_note"] = payload.note
                detail["closed_by"] = actor_id
                invoice.detail = detail
            session.add(invoice)
            session.commit()
            session.refresh(invoice)
            return invoice

    def void_invoice(
        self,
        tenant_id: str,
        invoice_id: str,
        actor_id: str,
        payload: BillingInvoiceVoidRequest,
    ) -> BillingInvoice:
        with self._session() as session:
            invoice = self._get_scoped_invoice(session, tenant_id, invoice_id)
            if invoice.status == BillingInvoiceStatus.VOID:
                raise ConflictError("invoice already void")
            if invoice.status == BillingInvoiceStatus.CLOSED:
                raise ConflictError("closed invoice cannot be voided")
            now = datetime.now(UTC)
            invoice.status = BillingInvoiceStatus.VOID
            invoice.voided_at = now
            invoice.updated_at = now
            detail = dict(invoice.detail)
            if payload.reason:
                detail["void_reason"] = payload.reason
            detail["voided_by"] = actor_id
            invoice.detail = detail
            session.add(invoice)
            session.commit()
            session.refresh(invoice)
            return invoice
