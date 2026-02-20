from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from app.adapters.dji_adapter import DjiAdapter
from app.adapters.fake_adapter import Ack, FakeAdapter
from app.adapters.mavlink_adapter import MavlinkAdapter
from app.domain.models import Command, CommandType, TelemetryNormalized


async def _collect_samples(
    stream: AsyncIterator[TelemetryNormalized],
    count: int,
) -> list[TelemetryNormalized]:
    samples: list[TelemetryNormalized] = []
    try:
        async for item in stream:
            samples.append(item)
            if len(samples) >= count:
                break
    finally:
        close_fn: Any = getattr(stream, "aclose", None)
        if callable(close_fn):
            await close_fn()
    return samples


def test_fake_adapter_streams_multi_drone_with_battery_decay() -> None:
    adapter = FakeAdapter(
        tenant_id="tenant-fake",
        telemetry_interval_seconds=0.0,
        battery_decay_per_tick=5.0,
        max_samples=3,
    )

    async def _run() -> tuple[list[TelemetryNormalized], list[TelemetryNormalized]]:
        await adapter.connect()
        a_samples, b_samples = await asyncio.gather(
            _collect_samples(adapter.start_stream("drone-a"), 3),
            _collect_samples(adapter.start_stream("drone-b"), 3),
        )
        await adapter.disconnect()
        return a_samples, b_samples

    samples_a, samples_b = asyncio.run(_run())
    assert len(samples_a) == 3
    assert len(samples_b) == 3
    assert samples_a[0].drone_id == "drone-a"
    assert samples_b[0].drone_id == "drone-b"
    assert samples_a[0].battery is not None
    assert samples_a[-1].battery is not None
    assert samples_a[0].battery.percent > samples_a[-1].battery.percent
    assert samples_a[0].position.lat != samples_b[0].position.lat


def test_fake_adapter_supports_alert_triggers() -> None:
    adapter = FakeAdapter(telemetry_interval_seconds=0.0, max_samples=1)
    adapter.set_trigger(
        "drone-alert",
        low_battery=True,
        lost_link=True,
        geofence_breach=True,
    )

    async def _run() -> TelemetryNormalized:
        await adapter.connect()
        sample = (await _collect_samples(adapter.start_stream("drone-alert"), 1))[0]
        await adapter.disconnect()
        return sample

    sample = asyncio.run(_run())
    assert sample.health["low_battery"] is True
    assert sample.health["link_lost"] is True
    assert sample.health["geofence_breach"] is True
    assert sample.link is not None
    assert sample.link.rssi is None
    assert sample.mode == "LINK_LOST"


def test_fake_adapter_command_ack_is_immediate() -> None:
    adapter = FakeAdapter(telemetry_interval_seconds=0.0, max_samples=1)
    command = Command(
        tenant_id="tenant-fake",
        drone_id="drone-cmd",
        type=CommandType.RTH,
        idempotency_key="fake-cmd-1",
    )

    async def _run() -> tuple[Ack, TelemetryNormalized]:
        ack = await adapter.send_command("drone-cmd", command)
        sample = (await _collect_samples(adapter.start_stream("drone-cmd"), 1))[0]
        return ack, sample

    ack, sample = asyncio.run(_run())
    assert ack.ok is True
    assert "FAKE ack" in ack.message
    assert sample.mode == "RTH"


def test_mavlink_adapter_simulation_mode_fallback() -> None:
    adapter = MavlinkAdapter(
        simulation_mode=True,
        tenant_id="tenant-mav",
        telemetry_interval_seconds=0.0,
        max_samples=1,
    )
    command = Command(
        tenant_id="tenant-mav",
        drone_id="drone-mav",
        type=CommandType.LAND,
        idempotency_key="mav-cmd-1",
    )

    async def _run() -> tuple[TelemetryNormalized, Ack]:
        await adapter.connect()
        sample = (await _collect_samples(adapter.start_stream("drone-mav"), 1))[0]
        ack = await adapter.send_command("drone-mav", command)
        await adapter.disconnect()
        return sample, ack

    sample, ack = asyncio.run(_run())
    assert sample.tenant_id == "tenant-mav"
    assert ack.ok is True
    assert ack.message.startswith("MAVLINK SIM")


def test_dji_adapter_simulation_skeleton_is_usable() -> None:
    adapter = DjiAdapter(
        simulation_mode=True,
        tenant_id="tenant-dji",
        telemetry_interval_seconds=0.0,
        max_samples=1,
    )
    command = Command(
        tenant_id="tenant-dji",
        drone_id="drone-dji",
        type=CommandType.HOLD,
        idempotency_key="dji-cmd-1",
    )

    async def _run() -> tuple[TelemetryNormalized, Ack]:
        await adapter.connect()
        sample = (await _collect_samples(adapter.start_stream("drone-dji"), 1))[0]
        ack = await adapter.send_command("drone-dji", command)
        await adapter.disconnect()
        return sample, ack

    sample, ack = asyncio.run(_run())
    assert sample.health["source"] == "dji"
    assert sample.health["simulation"] is True
    assert ack.ok is True
    assert ack.message.startswith("DJI SIM")
