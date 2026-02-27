from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import RLock
from typing import ClassVar, Protocol
from uuid import uuid4

from sqlmodel import Session, select

from app.adapters.dji_adapter import DjiAdapter
from app.adapters.fake_adapter import FakeAdapter
from app.adapters.mavlink_adapter import MavlinkAdapter
from app.domain.models import (
    DeviceIntegrationSessionRead,
    DeviceIntegrationSessionStatus,
    DeviceIntegrationStartRequest,
    Drone,
    DroneVendor,
    MapPointRead,
    TelemetryNormalized,
    VideoStreamCreateRequest,
    VideoStreamProtocol,
    VideoStreamRead,
    VideoStreamStatus,
    VideoStreamUpdateRequest,
)
from app.infra.db import get_engine
from app.infra.events import event_bus
from app.services.telemetry_service import NotFoundError as TelemetryNotFoundError
from app.services.telemetry_service import TelemetryService


class _IntegrationAdapter(Protocol):
    async def connect(self) -> None: ...

    async def disconnect(self) -> None: ...

    def start_stream(self, drone_id: str) -> AsyncIterator[TelemetryNormalized]: ...


class IntegrationError(Exception):
    pass


class NotFoundError(IntegrationError):
    pass


class ConflictError(IntegrationError):
    pass


@dataclass
class _DeviceSessionState:
    session_id: str
    tenant_id: str
    drone_id: str
    adapter_vendor: DroneVendor
    simulation_mode: bool
    telemetry_interval_seconds: float
    max_samples: int | None
    status: DeviceIntegrationSessionStatus = DeviceIntegrationSessionStatus.RUNNING
    samples_ingested: int = 0
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    stopped_at: datetime | None = None
    last_error: str | None = None
    task: asyncio.Task[None] | None = None


@dataclass
class _VideoStreamState:
    stream_id: str
    tenant_id: str
    stream_key: str
    protocol: VideoStreamProtocol
    endpoint: str
    label: str | None
    drone_id: str | None
    enabled: bool
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    detail: dict[str, object] = field(default_factory=dict)


class IntegrationService:
    _device_sessions: ClassVar[dict[str, dict[str, _DeviceSessionState]]] = {}
    _video_streams: ClassVar[dict[str, dict[str, _VideoStreamState]]] = {}
    _lock: ClassVar[RLock] = RLock()

    def __init__(self, *, telemetry_service: TelemetryService | None = None) -> None:
        self._telemetry_service = telemetry_service or TelemetryService()

    def _session(self) -> Session:
        return Session(get_engine(), expire_on_commit=False)

    def _get_scoped_drone(self, session: Session, tenant_id: str, drone_id: str) -> Drone:
        drone = session.exec(
            select(Drone).where(Drone.tenant_id == tenant_id).where(Drone.id == drone_id)
        ).first()
        if drone is None:
            raise NotFoundError("drone not found")
        return drone

    def _build_adapter(self, state: _DeviceSessionState) -> _IntegrationAdapter:
        if state.adapter_vendor == DroneVendor.FAKE:
            return FakeAdapter(
                tenant_id=state.tenant_id,
                telemetry_interval_seconds=state.telemetry_interval_seconds,
                max_samples=state.max_samples,
            )
        if state.adapter_vendor == DroneVendor.MAVLINK:
            return MavlinkAdapter(
                tenant_id=state.tenant_id,
                simulation_mode=state.simulation_mode,
                telemetry_interval_seconds=state.telemetry_interval_seconds,
                max_samples=state.max_samples,
            )
        if state.adapter_vendor == DroneVendor.DJI:
            return DjiAdapter(
                tenant_id=state.tenant_id,
                simulation_mode=state.simulation_mode,
                telemetry_interval_seconds=state.telemetry_interval_seconds,
                max_samples=state.max_samples,
            )
        raise ConflictError(f"adapter not available for vendor: {state.adapter_vendor}")

    @staticmethod
    def _to_device_session_read(state: _DeviceSessionState) -> DeviceIntegrationSessionRead:
        return DeviceIntegrationSessionRead(
            session_id=state.session_id,
            tenant_id=state.tenant_id,
            drone_id=state.drone_id,
            adapter_vendor=state.adapter_vendor,
            simulation_mode=state.simulation_mode,
            telemetry_interval_seconds=state.telemetry_interval_seconds,
            max_samples=state.max_samples,
            status=state.status,
            samples_ingested=state.samples_ingested,
            started_at=state.started_at,
            stopped_at=state.stopped_at,
            last_error=state.last_error,
        )

    def _get_scoped_session_state(self, tenant_id: str, session_id: str) -> _DeviceSessionState:
        tenant_sessions = self._device_sessions.get(tenant_id, {})
        state = tenant_sessions.get(session_id)
        if state is None:
            raise NotFoundError("device session not found")
        return state

    async def _run_session(self, state: _DeviceSessionState) -> None:
        adapter = self._build_adapter(state)
        try:
            await adapter.connect()
            async for sample in adapter.start_stream(state.drone_id):
                with self._lock:
                    current = self._get_scoped_session_state(state.tenant_id, state.session_id)
                    if current.status != DeviceIntegrationSessionStatus.RUNNING:
                        break
                    current.samples_ingested += 1
                self._telemetry_service.ingest(state.tenant_id, sample)

            publish_done = False
            with self._lock:
                current = self._get_scoped_session_state(state.tenant_id, state.session_id)
                if current.status == DeviceIntegrationSessionStatus.RUNNING:
                    current.status = DeviceIntegrationSessionStatus.COMPLETED
                    current.stopped_at = datetime.now(UTC)
                    publish_done = True
            if publish_done:
                event_bus.publish_dict(
                    "integration.device_session.completed",
                    state.tenant_id,
                    {
                        "session_id": state.session_id,
                        "drone_id": state.drone_id,
                        "adapter_vendor": state.adapter_vendor.value,
                        "samples_ingested": state.samples_ingested,
                    },
                )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            with self._lock:
                current = self._get_scoped_session_state(state.tenant_id, state.session_id)
                current.status = DeviceIntegrationSessionStatus.FAILED
                current.last_error = str(exc)
                current.stopped_at = datetime.now(UTC)
            event_bus.publish_dict(
                "integration.device_session.failed",
                state.tenant_id,
                {
                    "session_id": state.session_id,
                    "drone_id": state.drone_id,
                    "adapter_vendor": state.adapter_vendor.value,
                    "error": str(exc),
                },
            )
        finally:
            try:
                await adapter.disconnect()
            except Exception:
                return

    async def start_device_session(
        self,
        tenant_id: str,
        payload: DeviceIntegrationStartRequest,
    ) -> DeviceIntegrationSessionRead:
        with self._session() as session:
            drone = self._get_scoped_drone(session, tenant_id, payload.drone_id)
        adapter_vendor = payload.adapter_vendor or drone.vendor

        with self._lock:
            tenant_sessions = self._device_sessions.setdefault(tenant_id, {})
            for item in tenant_sessions.values():
                if item.drone_id == payload.drone_id and item.status == DeviceIntegrationSessionStatus.RUNNING:
                    raise ConflictError("device session already running for this drone")

            state = _DeviceSessionState(
                session_id=str(uuid4()),
                tenant_id=tenant_id,
                drone_id=payload.drone_id,
                adapter_vendor=adapter_vendor,
                simulation_mode=payload.simulation_mode,
                telemetry_interval_seconds=payload.telemetry_interval_seconds,
                max_samples=payload.max_samples,
            )
            tenant_sessions[state.session_id] = state

        state.task = asyncio.create_task(self._run_session(state))
        event_bus.publish_dict(
            "integration.device_session.started",
            tenant_id,
            {
                "session_id": state.session_id,
                "drone_id": state.drone_id,
                "adapter_vendor": state.adapter_vendor.value,
                "simulation_mode": state.simulation_mode,
            },
        )
        return self._to_device_session_read(state)

    async def stop_device_session(
        self,
        tenant_id: str,
        session_id: str,
    ) -> DeviceIntegrationSessionRead:
        task: asyncio.Task[None] | None = None
        with self._lock:
            state = self._get_scoped_session_state(tenant_id, session_id)
            if state.status == DeviceIntegrationSessionStatus.RUNNING:
                state.status = DeviceIntegrationSessionStatus.STOPPED
                state.stopped_at = datetime.now(UTC)
                task = state.task

        if task is not None:
            task.cancel()
            with suppress(BaseException):
                await task

        with self._lock:
            current = self._get_scoped_session_state(tenant_id, session_id)
            snapshot = self._to_device_session_read(current)

        event_bus.publish_dict(
            "integration.device_session.stopped",
            tenant_id,
            {
                "session_id": snapshot.session_id,
                "drone_id": snapshot.drone_id,
                "status": snapshot.status.value,
            },
        )
        return snapshot

    def get_device_session(self, tenant_id: str, session_id: str) -> DeviceIntegrationSessionRead:
        with self._lock:
            state = self._get_scoped_session_state(tenant_id, session_id)
            return self._to_device_session_read(state)

    def list_device_sessions(self, tenant_id: str) -> list[DeviceIntegrationSessionRead]:
        with self._lock:
            rows = list(self._device_sessions.get(tenant_id, {}).values())
            rows = sorted(rows, key=lambda item: item.started_at, reverse=True)
            return [self._to_device_session_read(item) for item in rows]

    def _get_scoped_stream_state(self, tenant_id: str, stream_id: str) -> _VideoStreamState:
        state = self._video_streams.get(tenant_id, {}).get(stream_id)
        if state is None:
            raise NotFoundError("video stream not found")
        return state

    def _resolve_stream_status(self, tenant_id: str, state: _VideoStreamState) -> tuple[VideoStreamStatus, MapPointRead | None]:
        if not state.enabled:
            return VideoStreamStatus.DISABLED, None
        if state.detail.get("last_error") is not None:
            return VideoStreamStatus.ERROR, None
        if state.drone_id is None:
            return VideoStreamStatus.STANDBY, None
        try:
            latest = self._telemetry_service.get_latest(tenant_id, state.drone_id)
        except TelemetryNotFoundError:
            return VideoStreamStatus.STANDBY, None
        return (
            VideoStreamStatus.LIVE,
            MapPointRead(
                lat=latest.position.lat,
                lon=latest.position.lon,
                alt_m=latest.position.alt_m,
                ts=latest.ts,
            ),
        )

    def _to_video_stream_read(self, tenant_id: str, state: _VideoStreamState) -> VideoStreamRead:
        status, linked = self._resolve_stream_status(tenant_id, state)
        return VideoStreamRead(
            stream_id=state.stream_id,
            stream_key=state.stream_key,
            protocol=state.protocol,
            endpoint=state.endpoint,
            label=state.label,
            drone_id=state.drone_id,
            enabled=state.enabled,
            status=status,
            linked_telemetry=linked,
            detail=dict(state.detail),
            created_at=state.created_at,
            updated_at=state.updated_at,
        )

    def create_video_stream(self, tenant_id: str, payload: VideoStreamCreateRequest) -> VideoStreamRead:
        if payload.drone_id is not None:
            with self._session() as session:
                _ = self._get_scoped_drone(session, tenant_id, payload.drone_id)

        with self._lock:
            tenant_streams = self._video_streams.setdefault(tenant_id, {})
            existing = next((item for item in tenant_streams.values() if item.stream_key == payload.stream_key), None)
            if existing is not None:
                raise ConflictError("video stream key already exists")
            stream = _VideoStreamState(
                stream_id=str(uuid4()),
                tenant_id=tenant_id,
                stream_key=payload.stream_key,
                protocol=payload.protocol,
                endpoint=payload.endpoint,
                label=payload.label,
                drone_id=payload.drone_id,
                enabled=payload.enabled,
            )
            tenant_streams[stream.stream_id] = stream
            snapshot = self._to_video_stream_read(tenant_id, stream)

        event_bus.publish_dict(
            "integration.video_stream.created",
            tenant_id,
            {
                "stream_id": snapshot.stream_id,
                "stream_key": snapshot.stream_key,
                "protocol": snapshot.protocol.value,
                "drone_id": snapshot.drone_id,
            },
        )
        return snapshot

    def update_video_stream(
        self,
        tenant_id: str,
        stream_id: str,
        payload: VideoStreamUpdateRequest,
    ) -> VideoStreamRead:
        if payload.drone_id is not None:
            with self._session() as session:
                _ = self._get_scoped_drone(session, tenant_id, payload.drone_id)

        with self._lock:
            state = self._get_scoped_stream_state(tenant_id, stream_id)
            if payload.protocol is not None:
                state.protocol = payload.protocol
            if payload.endpoint is not None:
                state.endpoint = payload.endpoint
            if payload.label is not None:
                state.label = payload.label
            if payload.drone_id is not None:
                state.drone_id = payload.drone_id
            if payload.enabled is not None:
                state.enabled = payload.enabled
            state.updated_at = datetime.now(UTC)
            snapshot = self._to_video_stream_read(tenant_id, state)

        event_bus.publish_dict(
            "integration.video_stream.updated",
            tenant_id,
            {
                "stream_id": snapshot.stream_id,
                "stream_key": snapshot.stream_key,
                "status": snapshot.status.value,
                "drone_id": snapshot.drone_id,
            },
        )
        return snapshot

    def delete_video_stream(self, tenant_id: str, stream_id: str) -> None:
        with self._lock:
            tenant_streams = self._video_streams.get(tenant_id, {})
            state = tenant_streams.pop(stream_id, None)
            if state is None:
                raise NotFoundError("video stream not found")

        event_bus.publish_dict(
            "integration.video_stream.deleted",
            tenant_id,
            {"stream_id": stream_id, "stream_key": state.stream_key},
        )

    def get_video_stream(self, tenant_id: str, stream_id: str) -> VideoStreamRead:
        with self._lock:
            state = self._get_scoped_stream_state(tenant_id, stream_id)
            return self._to_video_stream_read(tenant_id, state)

    def list_video_streams(self, tenant_id: str) -> list[VideoStreamRead]:
        with self._lock:
            rows = list(self._video_streams.get(tenant_id, {}).values())
            rows = sorted(rows, key=lambda item: item.updated_at, reverse=True)
            return [self._to_video_stream_read(tenant_id, item) for item in rows]
