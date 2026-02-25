from __future__ import annotations

import asyncio
import os
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.adapters.dji_adapter import DjiAdapter
from app.adapters.fake_adapter import FakeAdapter
from app.adapters.mavlink_adapter import MavlinkAdapter
from app.domain.models import (
    Command,
    CommandDispatchRequest,
    CommandRequestRecord,
    CommandStatus,
    ComplianceReasonCode,
    Drone,
    DroneVendor,
)
from app.infra.db import get_engine
from app.infra.events import event_bus
from app.services.compliance_service import ComplianceService, ComplianceViolationError


class CommandAdapter(Protocol):
    async def send_command(self, drone_id: str, command: Command) -> object: ...


AdapterFactory = Callable[[], CommandAdapter]


class CommandError(Exception):
    pass


class NotFoundError(CommandError):
    pass


class ConflictError(CommandError):
    pass


class CommandService:
    def __init__(
        self,
        *,
        ack_timeout_seconds: float | None = None,
        adapter_factories: dict[DroneVendor, AdapterFactory] | None = None,
    ) -> None:
        timeout = ack_timeout_seconds or float(os.getenv("COMMAND_ACK_TIMEOUT_SECONDS", "1.0"))
        self._ack_timeout_seconds = max(timeout, 0.01)
        self._adapter_factories: dict[DroneVendor, AdapterFactory] = adapter_factories or {
            DroneVendor.FAKE: lambda: FakeAdapter(),
            DroneVendor.MAVLINK: lambda: MavlinkAdapter(),
            DroneVendor.DJI: lambda: DjiAdapter(),
        }
        self._compliance = ComplianceService()

    def _session(self) -> Session:
        return Session(get_engine(), expire_on_commit=False)

    def _resolve_adapter(self, vendor: DroneVendor) -> CommandAdapter:
        factory = self._adapter_factories.get(vendor)
        if factory is None:
            raise ConflictError(f"adapter not available for vendor: {vendor}")
        return factory()

    def _get_scoped_command(
        self,
        session: Session,
        tenant_id: str,
        command_id: str,
    ) -> CommandRequestRecord:
        record = session.exec(
            select(CommandRequestRecord)
            .where(CommandRequestRecord.tenant_id == tenant_id)
            .where(CommandRequestRecord.id == command_id)
        ).first()
        if record is None:
            raise NotFoundError("command not found")
        return record

    def _get_scoped_drone(
        self,
        session: Session,
        tenant_id: str,
        drone_id: str,
    ) -> Drone:
        drone = session.exec(
            select(Drone)
            .where(Drone.tenant_id == tenant_id)
            .where(Drone.id == drone_id)
        ).first()
        if drone is None:
            raise NotFoundError("drone not found")
        return drone

    def _persist_outcome(
        self,
        *,
        tenant_id: str,
        command_id: str,
        status: CommandStatus,
        ack_ok: bool,
        ack_message: str,
    ) -> CommandRequestRecord:
        with self._session() as session:
            record = self._get_scoped_command(session, tenant_id, command_id)
            record.status = status
            record.ack_ok = ack_ok
            record.ack_message = ack_message
            record.attempts += 1
            record.updated_at = datetime.now(UTC)
            session.add(record)
            session.commit()
            session.refresh(record)
            return record

    def _raise_blocked_if_needed(self, record: CommandRequestRecord) -> None:
        if record.compliance_passed is not False:
            return
        reason_code = record.compliance_reason_code or ComplianceReasonCode.COMMAND_GEOFENCE_BLOCKED
        detail = dict(record.compliance_detail)
        detail.setdefault("command_id", record.id)
        detail.setdefault("drone_id", record.drone_id)
        raise ComplianceViolationError(
            reason_code,
            record.ack_message or "command blocked by compliance guardrail",
            detail=detail,
        )

    async def dispatch_command(
        self,
        *,
        tenant_id: str,
        actor_id: str,
        payload: CommandDispatchRequest,
    ) -> tuple[CommandRequestRecord, bool]:
        with self._session() as session:
            existing = session.exec(
                select(CommandRequestRecord)
                .where(CommandRequestRecord.tenant_id == tenant_id)
                .where(CommandRequestRecord.idempotency_key == payload.idempotency_key)
            ).first()
            if existing is not None:
                self._raise_blocked_if_needed(existing)
                return existing, False

            drone = self._get_scoped_drone(session, tenant_id, payload.drone_id)
            compliance_passed = True
            compliance_reason_code: ComplianceReasonCode | None = None
            compliance_detail: dict[str, object] = {}
            blocked_message: str | None = None
            try:
                compliance_detail = self._compliance.validate_command_precheck(
                    session=session,
                    tenant_id=tenant_id,
                    drone_id=payload.drone_id,
                    command_type=payload.type,
                    params=payload.params,
                )
            except ComplianceViolationError as exc:
                compliance_passed = False
                compliance_reason_code = exc.reason_code
                blocked_message = str(exc)
                compliance_detail = dict(exc.detail)
                compliance_detail.setdefault("reason_code", exc.reason_code.value)
                compliance_detail.setdefault("message", str(exc))

            record = CommandRequestRecord(
                tenant_id=tenant_id,
                drone_id=drone.id,
                command_type=payload.type,
                params=payload.params,
                idempotency_key=payload.idempotency_key,
                expect_ack=payload.expect_ack,
                status=CommandStatus.FAILED if not compliance_passed else CommandStatus.PENDING,
                ack_ok=False if not compliance_passed else None,
                ack_message=blocked_message,
                compliance_passed=compliance_passed,
                compliance_reason_code=compliance_reason_code,
                compliance_detail=compliance_detail,
                attempts=1 if not compliance_passed else 0,
                issued_by=actor_id,
            )
            if not compliance_passed:
                record.compliance_detail = dict(record.compliance_detail)
                record.compliance_detail.setdefault("command_id", record.id)
                record.compliance_detail.setdefault("drone_id", record.drone_id)
                record.compliance_detail.setdefault("command_type", payload.type.value)
            session.add(record)
            try:
                session.commit()
            except IntegrityError:
                session.rollback()
                fallback = session.exec(
                    select(CommandRequestRecord)
                    .where(CommandRequestRecord.tenant_id == tenant_id)
                    .where(CommandRequestRecord.idempotency_key == payload.idempotency_key)
                ).first()
                if fallback is None:
                    raise ConflictError("command idempotency conflict") from None
                self._raise_blocked_if_needed(fallback)
                return fallback, False
            session.refresh(record)
            command_id = record.id
            drone_vendor = drone.vendor
            drone_id = drone.id

            if not compliance_passed:
                event_bus.publish_dict(
                    "command.blocked",
                    tenant_id,
                    {
                        "command_id": record.id,
                        "drone_id": record.drone_id,
                        "status": record.status,
                        "reason_code": (
                            record.compliance_reason_code.value if record.compliance_reason_code else None
                        ),
                        "detail": record.compliance_detail,
                    },
                )
                self._raise_blocked_if_needed(record)

        event_bus.publish_dict(
            "command.requested",
            tenant_id,
            {
                "command_id": command_id,
                "drone_id": drone_id,
                "type": payload.type,
                "idempotency_key": payload.idempotency_key,
            },
        )

        adapter = self._resolve_adapter(drone_vendor)
        command = Command(
            tenant_id=tenant_id,
            command_id=command_id,
            drone_id=drone_id,
            type=payload.type,
            params=payload.params,
            idempotency_key=payload.idempotency_key,
            expect_ack=payload.expect_ack,
        )

        try:
            ack = await asyncio.wait_for(
                adapter.send_command(drone_id=drone_id, command=command),
                timeout=self._ack_timeout_seconds,
            )
        except TimeoutError:
            record = self._persist_outcome(
                tenant_id=tenant_id,
                command_id=command_id,
                status=CommandStatus.TIMEOUT,
                ack_ok=False,
                ack_message="command ack timeout",
            )
            event_bus.publish_dict(
                "command.timeout",
                tenant_id,
                {"command_id": record.id, "drone_id": record.drone_id, "status": record.status},
            )
            return record, True
        except Exception as exc:
            record = self._persist_outcome(
                tenant_id=tenant_id,
                command_id=command_id,
                status=CommandStatus.FAILED,
                ack_ok=False,
                ack_message=str(exc),
            )
            event_bus.publish_dict(
                "command.failed",
                tenant_id,
                {
                    "command_id": record.id,
                    "drone_id": record.drone_id,
                    "status": record.status,
                    "message": record.ack_message,
                },
            )
            return record, True

        ack_ok = bool(getattr(ack, "ok", False))
        ack_message = str(getattr(ack, "message", ""))
        status = CommandStatus.ACKED if ack_ok else CommandStatus.FAILED
        record = self._persist_outcome(
            tenant_id=tenant_id,
            command_id=command_id,
            status=status,
            ack_ok=ack_ok,
            ack_message=ack_message,
        )

        event_bus.publish_dict(
            "command.acked" if ack_ok else "command.failed",
            tenant_id,
            {
                "command_id": record.id,
                "drone_id": record.drone_id,
                "status": record.status,
                "ack_ok": record.ack_ok,
                "ack_message": record.ack_message,
            },
        )
        return record, True

    def get_command(self, tenant_id: str, command_id: str) -> CommandRequestRecord:
        with self._session() as session:
            return self._get_scoped_command(session, tenant_id, command_id)

    def list_commands(self, tenant_id: str) -> list[CommandRequestRecord]:
        with self._session() as session:
            statement = select(CommandRequestRecord).where(CommandRequestRecord.tenant_id == tenant_id)
            return list(session.exec(statement).all())
