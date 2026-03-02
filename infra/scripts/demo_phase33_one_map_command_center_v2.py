from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime, timedelta

import httpx
from demo_common import (
    add_observation,
    assert_status,
    auth_headers,
    bootstrap_admin,
    create_inspection_task,
    create_template,
    wait_ok,
)


async def _run() -> None:
    base_url = os.getenv("APP_BASE_URL", "http://app:8000").rstrip("/")
    timeout = httpx.Timeout(20.0)
    async with httpx.AsyncClient(base_url=base_url, timeout=timeout) as client:
        await wait_ok(client, "/healthz")
        await wait_ok(client, "/readyz")

        _tenant_id, token = await bootstrap_admin(client, "phase33")

        drone_resp = await client.post(
            "/api/registry/drones",
            json={"name": "phase33-drone", "vendor": "FAKE", "capabilities": {"camera": True}},
            headers=auth_headers(token),
        )
        assert_status(drone_resp, 201)
        drone_id = drone_resp.json()["id"]

        asset_resp = await client.post(
            "/api/assets",
            json={"asset_type": "UAV", "asset_code": "P33-UAV-01", "name": "phase33-uav"},
            headers=auth_headers(token),
        )
        assert_status(asset_resp, 201)
        asset_id = asset_resp.json()["id"]

        bind_resp = await client.post(
            f"/api/assets/{asset_id}/bind",
            json={"bound_to_drone_id": drone_id},
            headers=auth_headers(token),
        )
        assert_status(bind_resp, 200)

        template_id = await create_template(client, token, "phase33-template")
        task_id = await create_inspection_task(client, token, template_id, name="phase33-task")
        await add_observation(
            client,
            token,
            task_id,
            item_code="STRUCTURE",
            lat=30.5805,
            lon=114.3012,
            severity=2,
            note="phase33 observation",
        )

        incident_resp = await client.post(
            "/api/incidents",
            json={"title": "phase33-incident", "level": "P2", "location_geom": "POINT(114.302 30.581)"},
            headers=auth_headers(token),
        )
        assert_status(incident_resp, 201)

        base_ts = datetime.now(UTC)
        telemetry_samples = [
            (30.5800, 114.3000, 95.0, base_ts),
            (30.5808, 114.3008, 88.0, base_ts + timedelta(seconds=1)),
            (30.5815, 114.3014, 12.0, base_ts + timedelta(seconds=2)),
        ]
        for lat, lon, battery, ts in telemetry_samples:
            ingest_resp = await client.post(
                "/api/telemetry/ingest",
                json={
                    "tenant_id": "spoofed",
                    "drone_id": drone_id,
                    "ts": ts.isoformat(),
                    "position": {"lat": lat, "lon": lon, "alt_m": 120.0},
                    "battery": {"percent": battery},
                    "mode": "AUTO",
                    "health": {"low_battery": battery <= 20.0},
                },
                headers=auth_headers(token),
            )
            assert_status(ingest_resp, 200)

        overview_resp = await client.get("/api/map/overview?limit_per_layer=200", headers=auth_headers(token))
        assert_status(overview_resp, 200)
        overview = overview_resp.json()
        layer_names = {layer["layer"] for layer in overview.get("layers", [])}
        expected_layers = {"resources", "tasks", "airspace", "alerts", "events", "outcomes"}
        if layer_names != expected_layers:
            raise RuntimeError(f"unexpected phase33 map layer names: {layer_names}")
        for key in ("airspace_total", "outcomes_total", "generated_at"):
            if key not in overview:
                raise RuntimeError(f"phase33 overview missing key: {key}")

        ui_resp = await client.get(f"/ui/command-center?token={token}")
        assert_status(ui_resp, 200)
        body = ui_resp.text
        required_markers = [
            "一张图值守模式",
            "当前模式摘要",
            "事件时间轴",
            "当前焦点对象",
            "值守节奏",
        ]
        for marker in required_markers:
            if marker not in body:
                raise RuntimeError(f"phase33 command center missing marker: {marker}")

    print("demo_phase33_one_map_command_center_v2: ok")


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
