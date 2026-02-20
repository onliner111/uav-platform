from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from typing import Any

from app.adapters.fake_adapter import Ack, FakeAdapter
from app.domain.models import (
    Command,
    CommandType,
    MissionPlan,
    TelemetryBattery,
    TelemetryLink,
    TelemetryNormalized,
    TelemetryPosition,
)


class MavlinkAdapter(FakeAdapter):
    def __init__(
        self,
        *,
        connection_string: str | None = None,
        simulation_mode: bool | None = None,
        heartbeat_timeout_seconds: float = 3.0,
        tenant_id: str = "sim",
        telemetry_interval_seconds: float = 1.0,
        battery_decay_per_tick: float = 0.5,
        max_samples: int | None = None,
    ) -> None:
        super().__init__(
            tenant_id=tenant_id,
            telemetry_interval_seconds=telemetry_interval_seconds,
            battery_decay_per_tick=battery_decay_per_tick,
            max_samples=max_samples,
        )
        self._connection_string = connection_string or os.getenv(
            "MAVLINK_CONNECTION",
            "udp:127.0.0.1:14550",
        )
        self._heartbeat_timeout_seconds = max(heartbeat_timeout_seconds, 0.5)
        self._simulation_mode = self._resolve_simulation_mode(simulation_mode)

        self._mavutil: Any | None = None
        self._master: Any | None = None
        self._latest_position: tuple[float, float, float] | None = None
        self._latest_mode = "UNKNOWN"
        self._latest_battery_percent: float | None = None
        self._latest_battery_voltage: float | None = None

    def _resolve_simulation_mode(self, simulation_mode: bool | None) -> bool:
        if simulation_mode is not None:
            return simulation_mode
        raw = os.getenv("MAVLINK_SIMULATION_MODE", "1").strip().lower()
        return raw not in {"0", "false", "off"}

    def _load_mavutil(self) -> Any | None:
        try:
            from pymavlink import mavutil
        except Exception:
            return None
        return mavutil

    async def connect(self) -> None:
        if self._simulation_mode:
            return None

        mavutil = self._load_mavutil()
        if mavutil is None:
            self._simulation_mode = True
            return None

        try:
            master = mavutil.mavlink_connection(self._connection_string)
            await asyncio.to_thread(master.wait_heartbeat, timeout=self._heartbeat_timeout_seconds)
            self._mavutil = mavutil
            self._master = master
        except Exception:
            self._simulation_mode = True
            self._master = None
            self._mavutil = None
        return None

    async def disconnect(self) -> None:
        master = self._master
        self._master = None
        self._mavutil = None
        if master is not None and hasattr(master, "close"):
            await asyncio.to_thread(master.close)
        return None

    def _decode_mode(self, heartbeat_msg: Any) -> str:
        if self._mavutil is None:
            return "UNKNOWN"
        try:
            mode = self._mavutil.mode_string_v10(heartbeat_msg)
            if isinstance(mode, str) and mode:
                return mode
        except Exception:
            return "UNKNOWN"
        return "UNKNOWN"

    def _consume_mavlink_message(self, message: Any) -> None:
        msg_type = str(message.get_type())
        if msg_type == "GLOBAL_POSITION_INT":
            self._latest_position = (
                float(message.lat) / 10_000_000.0,
                float(message.lon) / 10_000_000.0,
                float(message.relative_alt) / 1000.0,
            )
            return
        if msg_type == "SYS_STATUS":
            percent = float(message.battery_remaining)
            self._latest_battery_percent = percent if percent >= 0 else None
            voltage = float(message.voltage_battery)
            self._latest_battery_voltage = voltage / 1000.0 if voltage > 0 else None
            return
        if msg_type == "HEARTBEAT":
            self._latest_mode = self._decode_mode(message)

    def _build_mavlink_telemetry(self, drone_id: str) -> TelemetryNormalized | None:
        if self._latest_position is None:
            return None
        lat, lon, alt_m = self._latest_position
        battery: TelemetryBattery | None = None
        if self._latest_battery_percent is not None or self._latest_battery_voltage is not None:
            battery = TelemetryBattery(
                percent=self._latest_battery_percent if self._latest_battery_percent is not None else 0.0,
                voltage=self._latest_battery_voltage,
            )
        return TelemetryNormalized(
            tenant_id=self._tenant_id,
            drone_id=drone_id,
            position=TelemetryPosition(lat=lat, lon=lon, alt_m=alt_m),
            battery=battery,
            link=TelemetryLink(rssi=None, latency_ms=None),
            mode=self._latest_mode,
            health={"source": "mavlink", "simulation": False},
        )

    async def start_stream(self, drone_id: str) -> AsyncIterator[TelemetryNormalized]:
        if self._simulation_mode or self._master is None:
            async for sample in super().start_stream(drone_id):
                yield sample
            return

        produced = 0
        while self._max_samples is None or produced < self._max_samples:
            timeout = max(self._telemetry_interval_seconds, 0.2)
            message = await asyncio.to_thread(
                self._master.recv_match,
                type=["HEARTBEAT", "GLOBAL_POSITION_INT", "SYS_STATUS"],
                blocking=True,
                timeout=timeout,
            )
            if message is None:
                if self._telemetry_interval_seconds > 0:
                    await asyncio.sleep(self._telemetry_interval_seconds)
                continue
            self._consume_mavlink_message(message)
            telemetry = self._build_mavlink_telemetry(drone_id)
            if telemetry is None:
                continue
            produced += 1
            yield telemetry

    def _command_to_mavlink_id(self, command_type: CommandType) -> int | None:
        if self._mavutil is None:
            return None
        mapping: dict[CommandType, str] = {
            CommandType.RTH: "MAV_CMD_NAV_RETURN_TO_LAUNCH",
            CommandType.HOLD: "MAV_CMD_NAV_LOITER_UNLIM",
            CommandType.LAND: "MAV_CMD_NAV_LAND",
        }
        name = mapping.get(command_type)
        if name is None:
            return None
        return int(getattr(self._mavutil.mavlink, name, 0)) or None

    async def send_command(self, drone_id: str, command: Command) -> Ack:
        if self._simulation_mode or self._master is None:
            ack = await super().send_command(drone_id, command)
            return Ack(ok=ack.ok, message=f"MAVLINK SIM {ack.message}")

        mav_cmd = self._command_to_mavlink_id(command.type)
        if mav_cmd is None:
            return Ack(ok=False, message=f"MAVLink command not supported: {command.type}")

        try:
            await asyncio.to_thread(
                self._master.mav.command_long_send,
                self._master.target_system,
                self._master.target_component,
                mav_cmd,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
            )
            self._latest_mode = command.type.value
            return Ack(ok=True, message=f"MAVLink command sent: {command.type}")
        except Exception as exc:
            return Ack(ok=False, message=f"MAVLink command failed: {exc}")

    async def upload_mission_plan(self, drone_id: str, plan: MissionPlan) -> None:
        if self._simulation_mode or self._master is None:
            await super().upload_mission_plan(drone_id, plan)
        return None

    def _synthetic_command(self, drone_id: str, command_type: CommandType) -> Command:
        return Command(
            tenant_id=self._tenant_id,
            drone_id=drone_id,
            type=command_type,
            idempotency_key=f"mavlink-{drone_id}-{command_type.value.lower()}",
        )

    async def start_mission(self, drone_id: str) -> None:
        if self._simulation_mode or self._master is None:
            await super().start_mission(drone_id)
            return None
        self._latest_mode = CommandType.START_MISSION.value
        return None

    async def abort(self, drone_id: str) -> None:
        if self._simulation_mode or self._master is None:
            await super().abort(drone_id)
            return None
        self._latest_mode = CommandType.ABORT_MISSION.value
        return None

    async def rth(self, drone_id: str) -> None:
        await self.send_command(drone_id, self._synthetic_command(drone_id, CommandType.RTH))
        return None

    async def land(self, drone_id: str) -> None:
        await self.send_command(drone_id, self._synthetic_command(drone_id, CommandType.LAND))
        return None

    async def hold(self, drone_id: str) -> None:
        await self.send_command(drone_id, self._synthetic_command(drone_id, CommandType.HOLD))
        return None
