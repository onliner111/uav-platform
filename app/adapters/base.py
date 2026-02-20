from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol

from app.domain.models import Command, MissionPlan, TelemetryNormalized


class AdapterAck(Protocol):
    ok: bool
    message: str


class BaseAdapter(Protocol):
    async def connect(self) -> None: ...

    async def disconnect(self) -> None: ...

    async def start_stream(self, drone_id: str) -> AsyncIterator[TelemetryNormalized]: ...

    async def send_command(self, drone_id: str, command: Command) -> AdapterAck: ...

    async def upload_mission_plan(self, drone_id: str, plan: MissionPlan) -> None: ...

    async def start_mission(self, drone_id: str) -> None: ...

    async def abort(self, drone_id: str) -> None: ...

    async def rth(self, drone_id: str) -> None: ...

    async def land(self, drone_id: str) -> None: ...

    async def hold(self, drone_id: str) -> None: ...

