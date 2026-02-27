from __future__ import annotations

import asyncio
import os
import time

import httpx
from demo_common import assert_status, auth_headers, bootstrap_admin, wait_ok


async def _wait_session_done(
    client: httpx.AsyncClient,
    token: str,
    session_id: str,
    timeout_seconds: float = 15.0,
) -> dict[str, object]:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        response = await client.get(
            f"/api/integration/device-sessions/{session_id}",
            headers=auth_headers(token),
        )
        assert_status(response, 200)
        payload = response.json()
        if payload["status"] in {"COMPLETED", "FAILED"}:
            return payload
        await asyncio.sleep(0.2)
    raise RuntimeError(f"timeout waiting for session {session_id} completion")


async def _run() -> None:
    base_url = os.getenv("APP_BASE_URL", "http://app:8000").rstrip("/")
    timeout = httpx.Timeout(20.0)

    async with httpx.AsyncClient(base_url=base_url, timeout=timeout) as client:
        await wait_ok(client, "/healthz")
        await wait_ok(client, "/readyz")

        _tenant_id, token = await bootstrap_admin(client, "phase19")

        drone_resp = await client.post(
            "/api/registry/drones",
            json={
                "name": "phase19-mavlink-drone",
                "vendor": "MAVLINK",
                "capabilities": {"camera": True, "stream": ["RTSP", "WEBRTC"]},
            },
            headers=auth_headers(token),
        )
        assert_status(drone_resp, 201)
        drone_id = drone_resp.json()["id"]

        start_resp = await client.post(
            "/api/integration/device-sessions/start",
            json={
                "drone_id": drone_id,
                "adapter_vendor": "MAVLINK",
                "simulation_mode": True,
                "telemetry_interval_seconds": 0.0,
                "max_samples": 5,
            },
            headers=auth_headers(token),
        )
        assert_status(start_resp, 201)
        session_id = start_resp.json()["session_id"]

        done = await _wait_session_done(client, token, session_id)
        if done["status"] != "COMPLETED":
            raise RuntimeError(f"device session expected COMPLETED, got: {done['status']}")
        if int(done["samples_ingested"]) < 5:
            raise RuntimeError("device session ingested less than expected samples")

        stream_resp = await client.post(
            "/api/integration/video-streams",
            json={
                "stream_key": "phase19-main",
                "protocol": "RTSP",
                "endpoint": "rtsp://demo.local/live/phase19-main",
                "label": "Phase19 Main Cam",
                "drone_id": drone_id,
                "enabled": True,
            },
            headers=auth_headers(token),
        )
        assert_status(stream_resp, 201)
        stream = stream_resp.json()
        if stream["status"] != "LIVE":
            raise RuntimeError(f"video stream expected LIVE, got: {stream['status']}")
        if stream.get("linked_telemetry") is None:
            raise RuntimeError("video stream expected linked telemetry")

        map_resp = await client.get("/api/map/overview?limit_per_layer=200", headers=auth_headers(token))
        assert_status(map_resp, 200)
        layers = map_resp.json().get("layers", [])
        resource_layer = next((item for item in layers if item.get("layer") == "resources"), None)
        if resource_layer is None:
            raise RuntimeError("map overview missing resources layer")
        if not any(item.get("id") == drone_id for item in resource_layer.get("items", [])):
            raise RuntimeError("map resources does not include phase19 drone")

    print("demo_phase19_real_device_video_integration: ok")


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
