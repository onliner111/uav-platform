from __future__ import annotations

import os
from collections.abc import AsyncIterator

from app.adapters.fake_adapter import Ack, FakeAdapter
from app.domain.models import Command, MissionPlan, TelemetryNormalized


class DjiAdapter(FakeAdapter):
    def __init__(
        self,
        *,
        simulation_mode: bool | None = None,
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
        self._simulation_mode = self._resolve_simulation_mode(simulation_mode)

    def _resolve_simulation_mode(self, simulation_mode: bool | None) -> bool:
        if simulation_mode is not None:
            return simulation_mode
        raw = os.getenv("DJI_SIMULATION_MODE", "1").strip().lower()
        return raw not in {"0", "false", "off"}

    async def connect(self) -> None:
        # SDK integration is intentionally deferred; keep simulation available.
        if not self._simulation_mode:
            self._simulation_mode = True
        return None

    async def disconnect(self) -> None:
        return None

    async def start_stream(self, drone_id: str) -> AsyncIterator[TelemetryNormalized]:
        async for sample in super().start_stream(drone_id):
            sample.health["source"] = "dji"
            sample.health["simulation"] = True
            yield sample

    async def send_command(self, drone_id: str, command: Command) -> Ack:
        ack = await super().send_command(drone_id, command)
        return Ack(ok=ack.ok, message=f"DJI SIM {ack.message}")

    async def upload_mission_plan(self, drone_id: str, plan: MissionPlan) -> None:
        await super().upload_mission_plan(drone_id, plan)
        return None
