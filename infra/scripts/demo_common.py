from __future__ import annotations

import asyncio
import time
from uuid import uuid4

import httpx


def assert_status(response: httpx.Response, expected: int | tuple[int, ...]) -> None:
    expected_codes = (expected,) if isinstance(expected, int) else expected
    if response.status_code not in expected_codes:
        raise RuntimeError(
            f"{response.request.method} {response.request.url} expected {expected_codes}, "
            f"got {response.status_code}: {response.text}"
        )


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def wait_ok(client: httpx.AsyncClient, path: str, timeout_seconds: float = 60.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            response = await client.get(path)
            if response.status_code == 200:
                return
        except httpx.HTTPError:
            pass
        await asyncio.sleep(1.0)
    raise RuntimeError(f"timeout waiting for {path}")


async def bootstrap_admin(client: httpx.AsyncClient, prefix: str) -> tuple[str, str]:
    run_id = uuid4().hex[:8]
    tenant_name = f"{prefix}-tenant-{run_id}"
    username = f"{prefix}-admin-{run_id}"
    password = f"pass-{run_id}"

    tenant_resp = await client.post("/api/identity/tenants", json={"name": tenant_name})
    assert_status(tenant_resp, 201)
    tenant_id = tenant_resp.json()["id"]

    bootstrap_resp = await client.post(
        "/api/identity/bootstrap-admin",
        json={"tenant_id": tenant_id, "username": username, "password": password},
    )
    assert_status(bootstrap_resp, 201)

    login_resp = await client.post(
        "/api/identity/dev-login",
        json={"tenant_id": tenant_id, "username": username, "password": password},
    )
    assert_status(login_resp, 200)
    token = login_resp.json()["access_token"]
    return tenant_id, token


async def create_template(client: httpx.AsyncClient, token: str, name: str = "city-inspection") -> str:
    template_resp = await client.post(
        "/api/inspection/templates",
        json={
            "name": name,
            "category": "urban",
            "description": "phase demo template",
            "is_active": True,
        },
        headers=auth_headers(token),
    )
    assert_status(template_resp, 201)
    template_id = template_resp.json()["id"]

    for idx, code in enumerate(["SIDEWALK_OCCUPY", "GARBAGE", "STALLING"], start=1):
        item_resp = await client.post(
            f"/api/inspection/templates/{template_id}/items",
            json={
                "code": code,
                "title": code.replace("_", " ").title(),
                "severity_default": idx,
                "required": True,
                "sort_order": idx,
            },
            headers=auth_headers(token),
        )
        assert_status(item_resp, 201)
    return template_id


async def create_inspection_task(
    client: httpx.AsyncClient,
    token: str,
    template_id: str,
    *,
    name: str = "phase-task",
    mission_id: str | None = None,
) -> str:
    payload = {
        "name": name,
        "template_id": template_id,
        "mission_id": mission_id,
        "area_geom": "POLYGON((114.30 30.58,114.31 30.58,114.31 30.59,114.30 30.59,114.30 30.58))",
        "priority": 3,
        "status": "SCHEDULED",
    }
    task_resp = await client.post("/api/inspection/tasks", json=payload, headers=auth_headers(token))
    assert_status(task_resp, 201)
    return task_resp.json()["id"]


async def add_observation(
    client: httpx.AsyncClient,
    token: str,
    task_id: str,
    *,
    item_code: str,
    lat: float,
    lon: float,
    severity: int,
    note: str,
) -> str:
    payload = {
        "position_lat": lat,
        "position_lon": lon,
        "alt_m": 80.0,
        "item_code": item_code,
        "severity": severity,
        "note": note,
        "confidence": 0.92,
    }
    resp = await client.post(
        f"/api/inspection/tasks/{task_id}/observations",
        json=payload,
        headers=auth_headers(token),
    )
    assert_status(resp, 201)
    return resp.json()["id"]
