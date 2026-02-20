from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from hashlib import sha1
from typing import Any

from app.domain.models import (
    Command,
    MissionPlan,
    TelemetryBattery,
    TelemetryLink,
    TelemetryNormalized,
    TelemetryPosition,
)


@dataclass
class Ack:
    ok: bool
    message: str


@dataclass
class DroneSimState:
    lat: float
    lon: float
    alt_m: float
    battery_percent: float = 100.0
    mode: str = "IDLE"
    lost_link: bool = False
    geofence_breach: bool = False
    low_battery: bool = False
    tick: int = 0
    mission_plan: MissionPlan | None = None
    extra_health: dict[str, Any] = field(default_factory=dict)


class FakeAdapter:
    def __init__(
        self,
        *,
        tenant_id: str = "sim",
        telemetry_interval_seconds: float = 1.0,
        battery_decay_per_tick: float = 0.5,
        max_samples: int | None = None,
        ack_delay_seconds: float = 0.0,
        force_timeout: bool = False,
        ack_ok: bool = True,
    ) -> None:
        self._tenant_id = tenant_id
        self._telemetry_interval_seconds = max(telemetry_interval_seconds, 0.0)
        self._battery_decay_per_tick = max(battery_decay_per_tick, 0.0)
        self._max_samples = max_samples
        self._ack_delay_seconds = max(ack_delay_seconds, 0.0)
        self._force_timeout = force_timeout
        self._ack_ok = ack_ok
        self._drone_states: dict[str, DroneSimState] = {}

    async def connect(self) -> None:
        return None

    async def disconnect(self) -> None:
        return None

    def _seed_for_drone(self, drone_id: str) -> int:
        digest = sha1(drone_id.encode(), usedforsecurity=False).hexdigest()
        return int(digest[:8], 16)

    def _ensure_state(self, drone_id: str) -> DroneSimState:
        existing = self._drone_states.get(drone_id)
        if existing is not None:
            return existing
        seed = self._seed_for_drone(drone_id)
        lat = 30.0 + (seed % 10_000) / 1_000_000.0
        lon = 114.0 + ((seed // 10_000) % 10_000) / 1_000_000.0
        alt_m = 100.0 + float(seed % 30)
        created = DroneSimState(lat=lat, lon=lon, alt_m=alt_m)
        self._drone_states[drone_id] = created
        return created

    def set_trigger(
        self,
        drone_id: str,
        *,
        low_battery: bool | None = None,
        lost_link: bool | None = None,
        geofence_breach: bool | None = None,
    ) -> None:
        state = self._ensure_state(drone_id)
        if low_battery is not None:
            state.low_battery = low_battery
        if lost_link is not None:
            state.lost_link = lost_link
            if lost_link:
                state.mode = "LINK_LOST"
        if geofence_breach is not None:
            state.geofence_breach = geofence_breach

    def clear_triggers(self, drone_id: str) -> None:
        self.set_trigger(
            drone_id,
            low_battery=False,
            lost_link=False,
            geofence_breach=False,
        )

    def _tick_state(self, drone_id: str) -> DroneSimState:
        state = self._ensure_state(drone_id)
        state.tick += 1

        if not state.geofence_breach:
            state.lat += 0.00005
            state.lon += 0.00004
        else:
            state.lat += 0.0015
            state.lon += 0.0012

        if not state.lost_link:
            state.alt_m = max(20.0, state.alt_m + (-0.2 if state.tick % 8 == 0 else 0.1))

        state.battery_percent = max(0.0, state.battery_percent - self._battery_decay_per_tick)
        if state.low_battery:
            state.battery_percent = min(state.battery_percent, 15.0)

        return state

    def _to_telemetry(self, drone_id: str, state: DroneSimState) -> TelemetryNormalized:
        health: dict[str, Any] = dict(state.extra_health)
        health["low_battery"] = state.low_battery or state.battery_percent <= 20.0
        health["link_lost"] = state.lost_link
        health["geofence_breach"] = state.geofence_breach

        link = TelemetryLink(rssi=None, latency_ms=3000) if state.lost_link else TelemetryLink(rssi=-58, latency_ms=42)
        return TelemetryNormalized(
            tenant_id=self._tenant_id,
            drone_id=drone_id,
            position=TelemetryPosition(
                lat=round(state.lat, 7),
                lon=round(state.lon, 7),
                alt_m=round(state.alt_m, 2),
            ),
            battery=TelemetryBattery(percent=round(state.battery_percent, 2), voltage=15.2, current=3.8),
            link=link,
            mode=state.mode,
            health=health,
        )

    async def start_stream(self, drone_id: str) -> AsyncIterator[TelemetryNormalized]:
        produced = 0
        while self._max_samples is None or produced < self._max_samples:
            state = self._tick_state(drone_id)
            yield self._to_telemetry(drone_id, state)
            produced += 1
            if self._telemetry_interval_seconds > 0:
                await asyncio.sleep(self._telemetry_interval_seconds)

    async def send_command(self, drone_id: str, command: Command) -> Ack:
        state = self._ensure_state(drone_id)
        params = command.params
        delay = float(params.get("_fake_delay_seconds", self._ack_delay_seconds))
        timeout_flag = bool(params.get("_fake_timeout", self._force_timeout))
        ack_ok = bool(params.get("_fake_ack_ok", self._ack_ok))
        if delay > 0:
            await asyncio.sleep(delay)
        if timeout_flag:
            # Simulate missing ACK until service timeout.
            await asyncio.sleep(3600)
        state.mode = command.type.value
        if command.type.value == "RTH":
            state.geofence_breach = False
        if command.type.value == "LAND":
            state.alt_m = 0.0
        if command.type.value == "HOLD":
            state.extra_health["holding"] = True
        return Ack(ok=ack_ok, message=f"FAKE ack for {command.type}")

    async def upload_mission_plan(self, drone_id: str, plan: MissionPlan) -> None:
        state = self._ensure_state(drone_id)
        state.mission_plan = plan
        return None

    async def start_mission(self, drone_id: str) -> None:
        state = self._ensure_state(drone_id)
        state.mode = "START_MISSION"
        return None

    async def abort(self, drone_id: str) -> None:
        state = self._ensure_state(drone_id)
        state.mode = "ABORT_MISSION"
        return None

    async def rth(self, drone_id: str) -> None:
        state = self._ensure_state(drone_id)
        state.mode = "RTH"
        state.geofence_breach = False
        return None

    async def land(self, drone_id: str) -> None:
        state = self._ensure_state(drone_id)
        state.mode = "LAND"
        state.alt_m = 0.0
        return None

    async def hold(self, drone_id: str) -> None:
        state = self._ensure_state(drone_id)
        state.mode = "HOLD"
        return None
