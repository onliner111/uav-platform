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

        _tenant_id, token = await bootstrap_admin(client, "phase10")

        drone_resp = await client.post(
            "/api/registry/drones",
            json={"name": "phase10-drone", "vendor": "FAKE", "capabilities": {"camera": True}},
            headers=auth_headers(token),
        )
        assert_status(drone_resp, 201)
        drone_id = drone_resp.json()["id"]

        asset_resp = await client.post(
            "/api/assets",
            json={"asset_type": "UAV", "asset_code": "P10-UAV-01", "name": "phase10-uav"},
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

        template_id = await create_template(client, token, "phase10-template")
        task_id = await create_inspection_task(client, token, template_id, name="phase10-task")
        _obs_id = await add_observation(
            client,
            token,
            task_id,
            item_code="GARBAGE",
            lat=30.5805,
            lon=114.3012,
            severity=2,
            note="phase10 observation",
        )

        incident_resp = await client.post(
            "/api/incidents",
            json={"title": "phase10-incident", "level": "P2", "location_geom": "POINT(114.302 30.581)"},
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
        if overview["resources_total"] < 2 or overview["tasks_total"] < 2 or overview["alerts_total"] < 1:
            raise RuntimeError(f"unexpected map overview payload: {overview}")
        layer_names = {layer["layer"] for layer in overview.get("layers", [])}
        if layer_names != {"resources", "tasks", "alerts", "events"}:
            raise RuntimeError(f"unexpected map layer names: {layer_names}")

        for layer_name in ("resources", "tasks", "alerts", "events"):
            layer_resp = await client.get(f"/api/map/layers/{layer_name}", headers=auth_headers(token))
            assert_status(layer_resp, 200)

        replay_resp = await client.get(
            f"/api/map/tracks/replay?drone_id={drone_id}&sample_step=2",
            headers=auth_headers(token),
        )
        assert_status(replay_resp, 200)
        replay_points = replay_resp.json().get("points", [])
        if len(replay_points) != 2:
            raise RuntimeError(f"unexpected replay points: {replay_points}")

        ui_resp = await client.get(f"/ui/command-center?token={token}")
        assert_status(ui_resp, 200)
        body = ui_resp.text
        required_markers = ["Layer Switch", "Track Replay", "Alert Highlight", "Video Slots"]
        for marker in required_markers:
            if marker not in body:
                raise RuntimeError(f"command center ui missing marker: {marker}")

    print("demo_phase10_one_map: ok")


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
