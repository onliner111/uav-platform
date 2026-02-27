from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.deps import get_current_claims, require_perm
from app.domain.models import (
    BillingInvoiceCloseRequest,
    BillingInvoiceDetailRead,
    BillingInvoiceGenerateRequest,
    BillingInvoiceLineRead,
    BillingInvoiceRead,
    BillingInvoiceStatus,
    BillingInvoiceVoidRequest,
    BillingPlanCreate,
    BillingPlanQuotaRead,
    BillingPlanRead,
    BillingQuotaCheckRead,
    BillingQuotaCheckRequest,
    BillingQuotaOverrideRead,
    BillingQuotaOverrideUpsertRequest,
    BillingSubscriptionCreate,
    BillingSubscriptionRead,
    BillingTenantQuotaSnapshotRead,
    BillingUsageEventRead,
    BillingUsageIngestRead,
    BillingUsageIngestRequest,
    BillingUsageSummaryRead,
)
from app.domain.permissions import PERM_BILLING_READ, PERM_BILLING_WRITE
from app.infra.audit import set_audit_context
from app.services.billing_service import BillingService, ConflictError, NotFoundError

router = APIRouter()


def get_billing_service() -> BillingService:
    return BillingService()


Claims = Annotated[dict[str, Any], Depends(get_current_claims)]
Service = Annotated[BillingService, Depends(get_billing_service)]


def _handle_billing_error(exc: Exception) -> None:
    if isinstance(exc, NotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if isinstance(exc, ConflictError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    raise exc


def _ensure_tenant_scope(path_tenant_id: str, claims: dict[str, Any]) -> None:
    if path_tenant_id != claims["tenant_id"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="tenant not found")


def _build_plan_read(plan_row: Any, quota_rows: list[Any]) -> BillingPlanRead:
    return BillingPlanRead(
        id=plan_row.id,
        tenant_id=plan_row.tenant_id,
        plan_code=plan_row.plan_code,
        display_name=plan_row.display_name,
        description=plan_row.description,
        billing_cycle=plan_row.billing_cycle,
        price_cents=plan_row.price_cents,
        currency=plan_row.currency,
        is_active=plan_row.is_active,
        created_by=plan_row.created_by,
        created_at=plan_row.created_at,
        updated_at=plan_row.updated_at,
        quotas=[BillingPlanQuotaRead.model_validate(item) for item in quota_rows],
    )


@router.post(
    "/plans",
    response_model=BillingPlanRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_perm(PERM_BILLING_WRITE))],
)
def create_plan(
    payload: BillingPlanCreate,
    request: Request,
    claims: Claims,
    service: Service,
) -> BillingPlanRead:
    try:
        plan, quotas = service.create_plan(claims["tenant_id"], claims["sub"], payload)
        set_audit_context(
            request,
            action="billing.plan.create",
            resource="/api/billing/plans",
            detail={"what": {"plan_id": plan.id, "plan_code": plan.plan_code}},
        )
        return _build_plan_read(plan, quotas)
    except (NotFoundError, ConflictError) as exc:
        _handle_billing_error(exc)
        raise


@router.get(
    "/plans",
    response_model=list[BillingPlanRead],
    dependencies=[Depends(require_perm(PERM_BILLING_READ))],
)
def list_plans(
    claims: Claims,
    service: Service,
    plan_code: str | None = None,
    is_active: bool | None = None,
) -> list[BillingPlanRead]:
    rows = service.list_plans(claims["tenant_id"], plan_code=plan_code, is_active=is_active)
    return [_build_plan_read(plan, quotas) for plan, quotas in rows]


@router.post(
    "/tenants/{tenant_id}/subscriptions",
    response_model=BillingSubscriptionRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_perm(PERM_BILLING_WRITE))],
)
def create_subscription(
    tenant_id: str,
    payload: BillingSubscriptionCreate,
    request: Request,
    claims: Claims,
    service: Service,
) -> BillingSubscriptionRead:
    _ensure_tenant_scope(tenant_id, claims)
    try:
        row = service.create_subscription(tenant_id, claims["sub"], payload)
        set_audit_context(
            request,
            action="billing.subscription.create",
            resource=f"/api/billing/tenants/{tenant_id}/subscriptions",
            detail={
                "what": {
                    "subscription_id": row.id,
                    "plan_id": row.plan_id,
                    "status": row.status.value,
                }
            },
        )
        return BillingSubscriptionRead.model_validate(row)
    except (NotFoundError, ConflictError) as exc:
        _handle_billing_error(exc)
        raise


@router.get(
    "/tenants/{tenant_id}/subscriptions",
    response_model=list[BillingSubscriptionRead],
    dependencies=[Depends(require_perm(PERM_BILLING_READ))],
)
def list_subscriptions(
    tenant_id: str,
    claims: Claims,
    service: Service,
) -> list[BillingSubscriptionRead]:
    _ensure_tenant_scope(tenant_id, claims)
    rows = service.list_subscriptions(tenant_id)
    return [BillingSubscriptionRead.model_validate(item) for item in rows]


@router.put(
    "/tenants/{tenant_id}/quotas/overrides",
    response_model=list[BillingQuotaOverrideRead],
    dependencies=[Depends(require_perm(PERM_BILLING_WRITE))],
)
def upsert_quota_overrides(
    tenant_id: str,
    payload: BillingQuotaOverrideUpsertRequest,
    request: Request,
    claims: Claims,
    service: Service,
) -> list[BillingQuotaOverrideRead]:
    _ensure_tenant_scope(tenant_id, claims)
    try:
        rows = service.upsert_quota_overrides(tenant_id, claims["sub"], payload)
        set_audit_context(
            request,
            action="billing.quota.override.upsert",
            resource=f"/api/billing/tenants/{tenant_id}/quotas/overrides",
            detail={"what": {"override_count": len(rows)}},
        )
        return [BillingQuotaOverrideRead.model_validate(item) for item in rows]
    except (NotFoundError, ConflictError) as exc:
        _handle_billing_error(exc)
        raise


@router.get(
    "/tenants/{tenant_id}/quotas/overrides",
    response_model=list[BillingQuotaOverrideRead],
    dependencies=[Depends(require_perm(PERM_BILLING_READ))],
)
def list_quota_overrides(
    tenant_id: str,
    claims: Claims,
    service: Service,
) -> list[BillingQuotaOverrideRead]:
    _ensure_tenant_scope(tenant_id, claims)
    rows = service.list_quota_overrides(tenant_id)
    return [BillingQuotaOverrideRead.model_validate(item) for item in rows]


@router.get(
    "/tenants/{tenant_id}/quotas",
    response_model=BillingTenantQuotaSnapshotRead,
    dependencies=[Depends(require_perm(PERM_BILLING_READ))],
)
def get_effective_quotas(
    tenant_id: str,
    claims: Claims,
    service: Service,
) -> BillingTenantQuotaSnapshotRead:
    _ensure_tenant_scope(tenant_id, claims)
    return service.get_effective_quotas(tenant_id)


@router.post(
    "/usage:ingest",
    response_model=BillingUsageIngestRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_perm(PERM_BILLING_WRITE))],
)
def ingest_usage(
    payload: BillingUsageIngestRequest,
    request: Request,
    claims: Claims,
    service: Service,
) -> BillingUsageIngestRead:
    try:
        event_row, deduplicated = service.ingest_usage_event(claims["tenant_id"], claims["sub"], payload)
        set_audit_context(
            request,
            action="billing.usage.ingest",
            resource="/api/billing/usage:ingest",
            detail={
                "what": {
                    "event_id": event_row.id,
                    "meter_key": event_row.meter_key,
                    "quantity": event_row.quantity,
                    "deduplicated": deduplicated,
                }
            },
        )
        return BillingUsageIngestRead(
            event=BillingUsageEventRead.model_validate(event_row),
            deduplicated=deduplicated,
        )
    except (NotFoundError, ConflictError) as exc:
        _handle_billing_error(exc)
        raise


@router.get(
    "/tenants/{tenant_id}/usage/summary",
    response_model=list[BillingUsageSummaryRead],
    dependencies=[Depends(require_perm(PERM_BILLING_READ))],
)
def list_usage_summary(
    tenant_id: str,
    claims: Claims,
    service: Service,
    meter_key: str | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
) -> list[BillingUsageSummaryRead]:
    _ensure_tenant_scope(tenant_id, claims)
    try:
        return service.list_usage_summary(
            tenant_id,
            meter_key=meter_key,
            from_date=from_date,
            to_date=to_date,
        )
    except (NotFoundError, ConflictError) as exc:
        _handle_billing_error(exc)
        raise


@router.post(
    "/tenants/{tenant_id}/quotas:check",
    response_model=BillingQuotaCheckRead,
    dependencies=[Depends(require_perm(PERM_BILLING_READ))],
)
def check_quota(
    tenant_id: str,
    payload: BillingQuotaCheckRequest,
    claims: Claims,
    service: Service,
) -> BillingQuotaCheckRead:
    _ensure_tenant_scope(tenant_id, claims)
    try:
        return service.check_quota(tenant_id, payload)
    except (NotFoundError, ConflictError) as exc:
        _handle_billing_error(exc)
        raise


@router.post(
    "/invoices:generate",
    response_model=BillingInvoiceRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_perm(PERM_BILLING_WRITE))],
)
def generate_invoice(
    payload: BillingInvoiceGenerateRequest,
    request: Request,
    claims: Claims,
    service: Service,
) -> BillingInvoiceRead:
    _ensure_tenant_scope(payload.tenant_id, claims)
    try:
        row = service.generate_invoice(payload.tenant_id, claims["sub"], payload)
        set_audit_context(
            request,
            action="billing.invoice.generate",
            resource="/api/billing/invoices:generate",
            detail={
                "what": {
                    "invoice_id": row.id,
                    "tenant_id": row.tenant_id,
                    "period_start": row.period_start.isoformat(),
                    "period_end": row.period_end.isoformat(),
                    "status": row.status.value,
                }
            },
        )
        return BillingInvoiceRead.model_validate(row)
    except (NotFoundError, ConflictError) as exc:
        _handle_billing_error(exc)
        raise


@router.get(
    "/tenants/{tenant_id}/invoices",
    response_model=list[BillingInvoiceRead],
    dependencies=[Depends(require_perm(PERM_BILLING_READ))],
)
def list_invoices(
    tenant_id: str,
    claims: Claims,
    service: Service,
    period_start: datetime | None = None,
    period_end: datetime | None = None,
    status: BillingInvoiceStatus | None = None,
) -> list[BillingInvoiceRead]:
    _ensure_tenant_scope(tenant_id, claims)
    rows = service.list_invoices(
        tenant_id,
        period_start=period_start,
        period_end=period_end,
        status=status,
    )
    return [BillingInvoiceRead.model_validate(item) for item in rows]


@router.get(
    "/invoices/{invoice_id}",
    response_model=BillingInvoiceDetailRead,
    dependencies=[Depends(require_perm(PERM_BILLING_READ))],
)
def get_invoice_detail(invoice_id: str, claims: Claims, service: Service) -> BillingInvoiceDetailRead:
    try:
        invoice, lines = service.get_invoice_detail(claims["tenant_id"], invoice_id)
        return BillingInvoiceDetailRead(
            invoice=BillingInvoiceRead.model_validate(invoice),
            lines=[BillingInvoiceLineRead.model_validate(item) for item in lines],
        )
    except (NotFoundError, ConflictError) as exc:
        _handle_billing_error(exc)
        raise


@router.post(
    "/invoices/{invoice_id}:close",
    response_model=BillingInvoiceRead,
    dependencies=[Depends(require_perm(PERM_BILLING_WRITE))],
)
def close_invoice(
    invoice_id: str,
    payload: BillingInvoiceCloseRequest,
    request: Request,
    claims: Claims,
    service: Service,
) -> BillingInvoiceRead:
    try:
        row = service.close_invoice(claims["tenant_id"], invoice_id, claims["sub"], payload)
        set_audit_context(
            request,
            action="billing.invoice.close",
            resource=f"/api/billing/invoices/{invoice_id}:close",
            detail={"what": {"invoice_id": row.id, "status": row.status.value}},
        )
        return BillingInvoiceRead.model_validate(row)
    except (NotFoundError, ConflictError) as exc:
        _handle_billing_error(exc)
        raise


@router.post(
    "/invoices/{invoice_id}:void",
    response_model=BillingInvoiceRead,
    dependencies=[Depends(require_perm(PERM_BILLING_WRITE))],
)
def void_invoice(
    invoice_id: str,
    payload: BillingInvoiceVoidRequest,
    request: Request,
    claims: Claims,
    service: Service,
) -> BillingInvoiceRead:
    try:
        row = service.void_invoice(claims["tenant_id"], invoice_id, claims["sub"], payload)
        set_audit_context(
            request,
            action="billing.invoice.void",
            resource=f"/api/billing/invoices/{invoice_id}:void",
            detail={"what": {"invoice_id": row.id, "status": row.status.value}},
        )
        return BillingInvoiceRead.model_validate(row)
    except (NotFoundError, ConflictError) as exc:
        _handle_billing_error(exc)
        raise
