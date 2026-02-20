from __future__ import annotations

import asyncio
import json
import os
import time
from typing import Any
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

import httpx
import websockets

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


def _to_ws_base_url(http_base_url: str) -> str:
    parsed = urlsplit(http_base_url)
    if parsed.scheme not in {"http", "https"}:
        raise RuntimeError(f"unsupported APP_BASE_URL scheme: {parsed.scheme}")
    ws_scheme = "wss" if parsed.scheme == "https" else "ws"
    return urlunsplit((ws_scheme, parsed.netloc, "", "", ""))


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
    ws_base_url = _to_ws_base_url(base_url)
    run_id = uuid4().hex[:8]
    tenant_name = f"smoke-tenant-{run_id}"
    username = f"smoke-admin-{run_id}"
    password = f"pass-{run_id}"

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
                "name": f"smoke-drone-{run_id}",
                "vendor": "FAKE",
                "capabilities": {"camera": True},
            },
            headers=_auth_headers(access_token),
        )
        _assert_status(drone_resp, 201)
        drone_body = drone_resp.json()
        drone_id = drone_body["id"]

        list_resp = await client.get("/api/registry/drones", headers=_auth_headers(access_token))
        _assert_status(list_resp, 200)
        listed_ids = {item["id"] for item in list_resp.json()}
        if drone_id not in listed_ids:
            raise RuntimeError("created drone missing from registry list")

        get_resp = await client.get(
            f"/api/registry/drones/{drone_id}",
            headers=_auth_headers(access_token),
        )
        _assert_status(get_resp, 200)

        update_resp = await client.patch(
            f"/api/registry/drones/{drone_id}",
            json={"capabilities": {"camera": True, "rth": True}},
            headers=_auth_headers(access_token),
        )
        _assert_status(update_resp, 200)
        updated = update_resp.json()
        if not updated["capabilities"].get("rth"):
            raise RuntimeError("registry patch failed to persist drone capabilities")

        adapter = FakeAdapter(
            tenant_id=tenant_id,
            telemetry_interval_seconds=0.0,
            battery_decay_per_tick=0.1,
            max_samples=1,
        )
        await adapter.connect()
        try:
            ws_url = f"{ws_base_url}/ws/drones?token={access_token}"
            async with websockets.connect(ws_url, open_timeout=10.0, close_timeout=5.0) as websocket:
                telemetry_sample = await _next_telemetry_sample(adapter, drone_id)
                ingest_resp = await client.post(
                    "/api/telemetry/ingest",
                    json=telemetry_sample,
                    headers=_auth_headers(access_token),
                )
                _assert_status(ingest_resp, 200)

                message = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                raw_message = message.decode() if isinstance(message, bytes) else message
                payload = json.loads(raw_message)
                if payload.get("tenant_id") != tenant_id or payload.get("drone_id") != drone_id:
                    raise RuntimeError(f"unexpected websocket payload: {payload}")

            latest_resp = await client.get(
                f"/api/telemetry/drones/{drone_id}/latest",
                headers=_auth_headers(access_token),
            )
            _assert_status(latest_resp, 200)
            latest_payload = latest_resp.json()
            if latest_payload.get("drone_id") != drone_id:
                raise RuntimeError("latest telemetry endpoint returned wrong drone payload")
        finally:
            await adapter.disconnect()

        delete_resp = await client.delete(
            f"/api/registry/drones/{drone_id}",
            headers=_auth_headers(access_token),
        )
        _assert_status(delete_resp, 204)

        list_after_delete = await client.get("/api/registry/drones", headers=_auth_headers(access_token))
        _assert_status(list_after_delete, 200)
        remaining_ids = {item["id"] for item in list_after_delete.json()}
        if drone_id in remaining_ids:
            raise RuntimeError("registry delete failed; drone still present")

    print("verify_smoke: healthz/readyz + registry CRUD + telemetry latest + ws ok")


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
