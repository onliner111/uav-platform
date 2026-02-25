from __future__ import annotations

import hashlib
import hmac
import json
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import true
from sqlmodel import Session, select

from app.domain.models import (
    OpenAdapterIngressEvent,
    OpenAdapterIngressRequest,
    OpenAdapterIngressStatus,
    OpenPlatformCredential,
    OpenPlatformCredentialCreate,
    OpenWebhookDelivery,
    OpenWebhookDeliveryStatus,
    OpenWebhookDispatchRequest,
    OpenWebhookEndpoint,
    OpenWebhookEndpointCreate,
)
from app.infra.db import get_engine
from app.infra.events import event_bus


class OpenPlatformError(Exception):
    pass


class NotFoundError(OpenPlatformError):
    pass


class ConflictError(OpenPlatformError):
    pass


class UnauthorizedError(OpenPlatformError):
    pass


class OpenPlatformService:
    def _session(self) -> Session:
        return Session(get_engine(), expire_on_commit=False)

    @staticmethod
    def _sign(secret: str, raw_body: bytes) -> str:
        return hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()

    def _get_scoped_credential(
        self,
        session: Session,
        tenant_id: str,
        credential_id: str,
    ) -> OpenPlatformCredential:
        row = session.exec(
            select(OpenPlatformCredential)
            .where(OpenPlatformCredential.tenant_id == tenant_id)
            .where(OpenPlatformCredential.id == credential_id)
        ).first()
        if row is None:
            raise NotFoundError("open platform credential not found")
        return row

    def _get_scoped_webhook(
        self,
        session: Session,
        tenant_id: str,
        endpoint_id: str,
    ) -> OpenWebhookEndpoint:
        row = session.exec(
            select(OpenWebhookEndpoint)
            .where(OpenWebhookEndpoint.tenant_id == tenant_id)
            .where(OpenWebhookEndpoint.id == endpoint_id)
        ).first()
        if row is None:
            raise NotFoundError("webhook endpoint not found")
        return row

    def create_credential(
        self,
        tenant_id: str,
        actor_id: str,
        payload: OpenPlatformCredentialCreate,
    ) -> OpenPlatformCredential:
        key_id = payload.key_id or f"key-{uuid4().hex[:12]}"
        api_key = payload.api_key or f"api-{uuid4().hex}"
        signing_secret = payload.signing_secret or f"sig-{uuid4().hex}"
        with self._session() as session:
            existing = session.exec(
                select(OpenPlatformCredential)
                .where(OpenPlatformCredential.tenant_id == tenant_id)
                .where(OpenPlatformCredential.key_id == key_id)
            ).first()
            if existing is not None:
                raise ConflictError("key_id already exists")

            row = OpenPlatformCredential(
                tenant_id=tenant_id,
                key_id=key_id,
                api_key=api_key,
                signing_secret=signing_secret,
                is_active=payload.is_active,
                created_by=actor_id,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return row

    def list_credentials(self, tenant_id: str) -> list[OpenPlatformCredential]:
        with self._session() as session:
            rows = list(
                session.exec(select(OpenPlatformCredential).where(OpenPlatformCredential.tenant_id == tenant_id)).all()
            )
            return sorted(rows, key=lambda item: item.created_at, reverse=True)

    def create_webhook(
        self,
        tenant_id: str,
        actor_id: str,
        payload: OpenWebhookEndpointCreate,
    ) -> OpenWebhookEndpoint:
        with self._session() as session:
            if payload.credential_id is not None:
                _ = self._get_scoped_credential(session, tenant_id, payload.credential_id)

            row = OpenWebhookEndpoint(
                tenant_id=tenant_id,
                name=payload.name,
                endpoint_url=payload.endpoint_url,
                event_type=payload.event_type,
                credential_id=payload.credential_id,
                auth_type=payload.auth_type,
                is_active=payload.is_active,
                extra_headers=payload.extra_headers,
                created_by=actor_id,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return row

    def list_webhooks(self, tenant_id: str, *, event_type: str | None = None) -> list[OpenWebhookEndpoint]:
        with self._session() as session:
            statement = select(OpenWebhookEndpoint).where(OpenWebhookEndpoint.tenant_id == tenant_id)
            if event_type is not None:
                statement = statement.where(OpenWebhookEndpoint.event_type == event_type)
            rows = list(session.exec(statement).all())
            return sorted(rows, key=lambda item: item.created_at, reverse=True)

    def dispatch_webhook_test(
        self,
        tenant_id: str,
        endpoint_id: str,
        payload: OpenWebhookDispatchRequest,
    ) -> OpenWebhookDelivery:
        with self._session() as session:
            endpoint = self._get_scoped_webhook(session, tenant_id, endpoint_id)
            if not endpoint.is_active:
                raise ConflictError("webhook endpoint is inactive")

            body = {
                "event_type": endpoint.event_type,
                "payload": payload.payload,
                "sent_at": datetime.now(UTC).isoformat(),
            }
            raw_body = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")

            signature: str | None = None
            request_headers = dict(endpoint.extra_headers)
            status = OpenWebhookDeliveryStatus.SENT
            detail = {"delivery_mode": "simulated"}
            if endpoint.credential_id is not None:
                credential = self._get_scoped_credential(session, tenant_id, endpoint.credential_id)
                if not credential.is_active:
                    status = OpenWebhookDeliveryStatus.SKIPPED
                    detail["reason"] = "credential_inactive"
                else:
                    signature = self._sign(credential.signing_secret, raw_body)
                    request_headers["X-Open-Key-Id"] = credential.key_id
                    request_headers["X-Open-Signature"] = signature
            else:
                status = OpenWebhookDeliveryStatus.SKIPPED
                detail["reason"] = "missing_credential"

            row = OpenWebhookDelivery(
                tenant_id=tenant_id,
                endpoint_id=endpoint.id,
                event_type=endpoint.event_type,
                payload=body,
                signature=signature,
                request_headers=request_headers,
                status=status,
                detail=detail,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return row

    def _find_credential_by_key_id(
        self,
        session: Session,
        key_id: str,
    ) -> OpenPlatformCredential:
        row = session.exec(
            select(OpenPlatformCredential)
            .where(OpenPlatformCredential.key_id == key_id)
            .where(OpenPlatformCredential.is_active == true())
        ).first()
        if row is None:
            raise UnauthorizedError("invalid key id")
        return row

    def ingest_adapter_event(
        self,
        *,
        key_id: str,
        api_key: str,
        signature: str,
        payload: OpenAdapterIngressRequest,
        raw_body: bytes,
    ) -> OpenAdapterIngressEvent:
        with self._session() as session:
            credential = self._find_credential_by_key_id(session, key_id)
            signature_valid = True
            status = OpenAdapterIngressStatus.ACCEPTED
            detail = {}

            if not hmac.compare_digest(credential.api_key, api_key):
                signature_valid = False
                status = OpenAdapterIngressStatus.REJECTED
                detail["reason"] = "api_key_mismatch"
            else:
                expected_signature = self._sign(credential.signing_secret, raw_body)
                if not hmac.compare_digest(expected_signature, signature):
                    signature_valid = False
                    status = OpenAdapterIngressStatus.REJECTED
                    detail["reason"] = "signature_mismatch"
                    detail["expected_signature"] = expected_signature

            row = OpenAdapterIngressEvent(
                tenant_id=credential.tenant_id,
                key_id=credential.key_id,
                event_type=payload.event_type,
                payload=payload.payload,
                signature_valid=signature_valid,
                status=status,
                detail=detail,
            )
            session.add(row)
            session.commit()
            session.refresh(row)

        if not signature_valid:
            raise UnauthorizedError("signature validation failed")

        event_bus.publish_dict(
            "open.adapter.ingested",
            row.tenant_id,
            {"event_id": row.id, "key_id": row.key_id, "event_type": row.event_type},
        )
        return row

    def list_adapter_events(self, tenant_id: str) -> list[OpenAdapterIngressEvent]:
        with self._session() as session:
            rows = list(
                session.exec(
                    select(OpenAdapterIngressEvent).where(OpenAdapterIngressEvent.tenant_id == tenant_id)
                ).all()
            )
            return sorted(rows, key=lambda item: item.created_at, reverse=True)
