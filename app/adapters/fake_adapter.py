from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass

from app.domain.models import Command, MissionPlan, TelemetryNormalized


@dataclass
class Ack:
    ok: bool
    message: str


class FakeAdapter:
    def __init__(
        self,
        *,
        ack_delay_seconds: float = 0.0,
        force_timeout: bool = False,
        ack_ok: bool = True,
    ) -> None:
        self._ack_delay_seconds = max(ack_delay_seconds, 0.0)
        self._force_timeout = force_timeout
        self._ack_ok = ack_ok

    async def connect(self) -> None:
        return None

    async def disconnect(self) -> None:
        return None

    async def start_stream(self, drone_id: str) -> AsyncIterator[TelemetryNormalized]:
        if False:
            yield  # pragma: no cover
        return

    async def send_command(self, drone_id: str, command: Command) -> Ack:
        params = command.params
        delay = float(params.get("_fake_delay_seconds", self._ack_delay_seconds))
        timeout_flag = bool(params.get("_fake_timeout", self._force_timeout))
        ack_ok = bool(params.get("_fake_ack_ok", self._ack_ok))
        if delay > 0:
            await asyncio.sleep(delay)
        if timeout_flag:
            # Simulate missing ACK until service timeout.
            await asyncio.sleep(3600)
        return Ack(ok=ack_ok, message=f"FAKE ack for {command.type}")

    async def upload_mission_plan(self, drone_id: str, plan: MissionPlan) -> None:
        return None

    async def start_mission(self, drone_id: str) -> None:
        return None

    async def abort(self, drone_id: str) -> None:
        return None

    async def rth(self, drone_id: str) -> None:
        return None

    async def land(self, drone_id: str) -> None:
        return None

    async def hold(self, drone_id: str) -> None:
        return None
