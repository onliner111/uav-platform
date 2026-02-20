from __future__ import annotations

import asyncio
import os
import time
from typing import Any
from uuid import uuid4

import httpx

from app.adapters.fake_adapter import FakeAdapter


def _assert_status(response: httpx.Response, expected: int | tuple[int, ...]) -> None:
    expected_codes = (expected,) if isinstance(expected, int) else expected
    if response.status_code not in expected_codes:
        raise RuntimeError(
            f"{response.request.method} {response.request.url} expected {expected_codes}, "
            f"got {response.status_code}: {response.text}"
        )


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _wait_ok(client: httpx.AsyncClient, path: str, timeout_seconds: float = 60.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_status = "n/a"
    last_body = ""
    while time.monotonic() < deadline:
        try:
            response = await client.get(path)
            if response.status_code == 200:
                return
            last_status = str(response.status_code)
            last_body = response.text
        except httpx.HTTPError as exc:
            last_status = "http_error"
            last_body = str(exc)
        await asyncio.sleep(1.0)
    raise RuntimeError(f"timeout waiting for {path}, last_status={last_status}, detail={last_body}")


async def _next_telemetry_sample(adapter: FakeAdapter, drone_id: str) -> dict[str, Any]:
    async for sample in adapter.start_stream(drone_id):
        return sample.model_dump(mode="json")
    raise RuntimeError("fake adapter produced no telemetry sample")


async def _run() -> None:
    base_url = os.getenv("APP_BASE_URL", "http://app:8000").rstrip("/")
    run_id = uuid4().hex[:8]
    tenant_name = f"e2e-tenant-{run_id}"
    username = f"admin-{run_id}"
    password = f"pass-{run_id}"
    drone_name = f"drone-{run_id}"

    timeout = httpx.Timeout(20.0)
    async with httpx.AsyncClient(base_url=base_url, timeout=timeout) as client:
        await _wait_ok(client, "/healthz")
        await _wait_ok(client, "/readyz")

        tenant_resp = await client.post("/api/identity/tenants", json={"name": tenant_name})
        _assert_status(tenant_resp, 201)
        tenant_id = tenant_resp.json()["id"]

        bootstrap_resp = await client.post(
            "/api/identity/bootstrap-admin",
            json={"tenant_id": tenant_id, "username": username, "password": password},
        )
        _assert_status(bootstrap_resp, 201)

        login_resp = await client.post(
            "/api/identity/dev-login",
            json={"tenant_id": tenant_id, "username": username, "password": password},
        )
        _assert_status(login_resp, 200)
        access_token = login_resp.json()["access_token"]

        drone_resp = await client.post(
            "/api/registry/drones",
            json={
                "name": drone_name,
                "vendor": "FAKE",
                "capabilities": {"rth": True, "camera": True},
            },
            headers=_auth_headers(access_token),
        )
        _assert_status(drone_resp, 201)
        drone_id = drone_resp.json()["id"]

        adapter = FakeAdapter(
            tenant_id=tenant_id,
            telemetry_interval_seconds=0.0,
            battery_decay_per_tick=0.2,
            max_samples=1,
        )
        await adapter.connect()
        try:
            base_telemetry = await _next_telemetry_sample(adapter, drone_id)
            ingest_resp = await client.post(
                "/api/telemetry/ingest",
                json=base_telemetry,
                headers=_auth_headers(access_token),
            )
            _assert_status(ingest_resp, 200)

            mission_resp = await client.post(
                "/api/mission/missions",
                json={
                    "name": f"inspection-{run_id}",
                    "drone_id": drone_id,
                    "type": "ROUTE_WAYPOINTS",
                    "payload": {"waypoints": [{"lat": 30.1, "lon": 114.2, "alt_m": 120.0}]},
                    "constraints": {"max_alt": 150},
                },
                headers=_auth_headers(access_token),
            )
            _assert_status(mission_resp, 201)
            mission_id = mission_resp.json()["id"]

            approve_resp = await client.post(
                f"/api/mission/missions/{mission_id}/approve",
                json={"decision": "APPROVE", "comment": "phase9 demo approval"},
                headers=_auth_headers(access_token),
            )
            _assert_status(approve_resp, 200)
            if approve_resp.json()["state"] != "APPROVED":
                raise RuntimeError("mission approval failed to reach APPROVED state")

            command_resp = await client.post(
                "/api/command/commands",
                json={
                    "drone_id": drone_id,
                    "type": "RTH",
                    "params": {"reason": "phase9_demo"},
                    "idempotency_key": f"phase9-rth-{run_id}",
                    "expect_ack": True,
                },
                headers=_auth_headers(access_token),
            )
            _assert_status(command_resp, (200, 201))
            command_body = command_resp.json()
            if command_body["status"] != "ACKED" or command_body["ack_ok"] is not True:
                raise RuntimeError(f"command was not ACKED: {command_body}")

            adapter.set_trigger(drone_id, low_battery=True)
            low_battery_telemetry = await _next_telemetry_sample(adapter, drone_id)
            low_ingest_resp = await client.post(
                "/api/telemetry/ingest",
                json=low_battery_telemetry,
                headers=_auth_headers(access_token),
            )
            _assert_status(low_ingest_resp, 200)

            alerts_resp = await client.get(
                "/api/alert/alerts",
                params={"drone_id": drone_id},
                headers=_auth_headers(access_token),
            )
            _assert_status(alerts_resp, 200)
            alerts = alerts_resp.json()
            low_battery_alerts = [item for item in alerts if item.get("alert_type") == "LOW_BATTERY"]
            if not low_battery_alerts:
                raise RuntimeError("LOW_BATTERY alert not found after low battery telemetry")
        finally:
            await adapter.disconnect()

    print("demo_e2e: phase9 flow ok")


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
