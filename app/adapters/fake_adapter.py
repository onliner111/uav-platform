from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass

from app.domain.models import Command, MissionPlan, TelemetryNormalized


@dataclass
class Ack:
    ok: bool
    message: str


class FakeAdapter:
    async def connect(self) -> None:
        return None

    async def disconnect(self) -> None:
        return None

    async def start_stream(self, drone_id: str) -> AsyncIterator[TelemetryNormalized]:
        if False:
            yield  # pragma: no cover
        return

    async def send_command(self, drone_id: str, command: Command) -> Ack:
        return Ack(ok=True, message=f"FAKE ack for {command.type}")

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

