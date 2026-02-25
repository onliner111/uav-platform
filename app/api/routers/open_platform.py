from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from app.api.deps import get_current_claims, require_perm
from app.domain.models import (
    OpenAdapterIngressRead,
    OpenAdapterIngressRequest,
    OpenPlatformCredentialCreate,
    OpenPlatformCredentialRead,
    OpenWebhookDeliveryRead,
    OpenWebhookDispatchRequest,
    OpenWebhookEndpointCreate,
    OpenWebhookEndpointRead,
)
from app.domain.permissions import PERM_REPORTING_READ, PERM_REPORTING_WRITE
from app.infra.audit import set_audit_context
from app.services.open_platform_service import (
    ConflictError,
    NotFoundError,
    OpenPlatformService,
    UnauthorizedError,
)

router = APIRouter()


def get_open_platform_service() -> OpenPlatformService:
    return OpenPlatformService()


Claims = Annotated[dict[str, Any], Depends(get_current_claims)]
Service = Annotated[OpenPlatformService, Depends(get_open_platform_service)]


def _handle_open_platform_error(exc: Exception) -> None:
    if isinstance(exc, NotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if isinstance(exc, UnauthorizedError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    if isinstance(exc, ConflictError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    raise exc


@router.post(
    "/credentials",
    response_model=OpenPlatformCredentialRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_perm(PERM_REPORTING_WRITE))],
)
def create_credential(
    payload: OpenPlatformCredentialCreate,
    request: Request,
    claims: Claims,
    service: Service,
) -> OpenPlatformCredentialRead:
    try:
        row = service.create_credential(claims["tenant_id"], claims["sub"], payload)
        set_audit_context(
            request,
            action="open_platform.credential.create",
            resource="/api/open-platform/credentials",
            detail={"what": {"credential_id": row.id, "key_id": row.key_id}},
        )
        return OpenPlatformCredentialRead.model_validate(row)
    except (NotFoundError, UnauthorizedError, ConflictError) as exc:
        _handle_open_platform_error(exc)
        raise


@router.get(
    "/credentials",
    response_model=list[OpenPlatformCredentialRead],
    dependencies=[Depends(require_perm(PERM_REPORTING_READ))],
)
def list_credentials(claims: Claims, service: Service) -> list[OpenPlatformCredentialRead]:
    rows = service.list_credentials(claims["tenant_id"])
    return [OpenPlatformCredentialRead.model_validate(item) for item in rows]


@router.post(
    "/webhooks",
    response_model=OpenWebhookEndpointRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_perm(PERM_REPORTING_WRITE))],
)
def create_webhook(
    payload: OpenWebhookEndpointCreate,
    request: Request,
    claims: Claims,
    service: Service,
) -> OpenWebhookEndpointRead:
    try:
        row = service.create_webhook(claims["tenant_id"], claims["sub"], payload)
        set_audit_context(
            request,
            action="open_platform.webhook.create",
            resource="/api/open-platform/webhooks",
            detail={"what": {"endpoint_id": row.id, "event_type": row.event_type}},
        )
        return OpenWebhookEndpointRead.model_validate(row)
    except (NotFoundError, UnauthorizedError, ConflictError) as exc:
        _handle_open_platform_error(exc)
        raise


@router.get(
    "/webhooks",
    response_model=list[OpenWebhookEndpointRead],
    dependencies=[Depends(require_perm(PERM_REPORTING_READ))],
)
def list_webhooks(
    claims: Claims,
    service: Service,
    event_type: str | None = None,
) -> list[OpenWebhookEndpointRead]:
    rows = service.list_webhooks(claims["tenant_id"], event_type=event_type)
    return [OpenWebhookEndpointRead.model_validate(item) for item in rows]


@router.post(
    "/webhooks/{endpoint_id}/dispatch-test",
    response_model=OpenWebhookDeliveryRead,
    dependencies=[Depends(require_perm(PERM_REPORTING_WRITE))],
)
def dispatch_webhook_test(
    endpoint_id: str,
    payload: OpenWebhookDispatchRequest,
    request: Request,
    claims: Claims,
    service: Service,
) -> OpenWebhookDeliveryRead:
    try:
        row = service.dispatch_webhook_test(claims["tenant_id"], endpoint_id, payload)
        set_audit_context(
            request,
            action="open_platform.webhook.dispatch_test",
            resource=f"/api/open-platform/webhooks/{endpoint_id}/dispatch-test",
            detail={
                "what": {
                    "delivery_id": row.id,
                    "endpoint_id": row.endpoint_id,
                    "status": row.status.value,
                }
            },
        )
        return OpenWebhookDeliveryRead.model_validate(row)
    except (NotFoundError, UnauthorizedError, ConflictError) as exc:
        _handle_open_platform_error(exc)
        raise


@router.post(
    "/adapters/events/ingest",
    response_model=OpenAdapterIngressRead,
    status_code=status.HTTP_201_CREATED,
)
async def ingest_adapter_event(
    payload: OpenAdapterIngressRequest,
    request: Request,
    service: Service,
    x_open_key_id: Annotated[str, Header(alias="X-Open-Key-Id")],
    x_open_api_key: Annotated[str, Header(alias="X-Open-Api-Key")],
    x_open_signature: Annotated[str, Header(alias="X-Open-Signature")],
) -> OpenAdapterIngressRead:
    raw_body = await request.body()
    try:
        row = service.ingest_adapter_event(
            key_id=x_open_key_id,
            api_key=x_open_api_key,
            signature=x_open_signature,
            payload=payload,
            raw_body=raw_body,
        )
        set_audit_context(
            request,
            action="open_platform.adapter.ingest",
            resource="/api/open-platform/adapters/events/ingest",
            detail={"what": {"event_id": row.id, "tenant_id": row.tenant_id, "key_id": row.key_id}},
        )
        return OpenAdapterIngressRead.model_validate(row)
    except (NotFoundError, UnauthorizedError, ConflictError) as exc:
        _handle_open_platform_error(exc)
        raise


@router.get(
    "/adapters/events",
    response_model=list[OpenAdapterIngressRead],
    dependencies=[Depends(require_perm(PERM_REPORTING_READ))],
)
def list_adapter_events(claims: Claims, service: Service) -> list[OpenAdapterIngressRead]:
    rows = service.list_adapter_events(claims["tenant_id"])
    return [OpenAdapterIngressRead.model_validate(item) for item in rows]
