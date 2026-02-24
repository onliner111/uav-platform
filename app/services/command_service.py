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
    Drone,
    DroneVendor,
)
from app.infra.db import get_engine
from app.infra.events import event_bus


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
                return existing, False

            drone = self._get_scoped_drone(session, tenant_id, payload.drone_id)

            record = CommandRequestRecord(
                tenant_id=tenant_id,
                drone_id=drone.id,
                command_type=payload.type,
                params=payload.params,
                idempotency_key=payload.idempotency_key,
                expect_ack=payload.expect_ack,
                status=CommandStatus.PENDING,
                issued_by=actor_id,
            )
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
                return fallback, False
            session.refresh(record)
            command_id = record.id
            drone_vendor = drone.vendor
            drone_id = drone.id

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
