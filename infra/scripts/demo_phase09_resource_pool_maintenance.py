from __future__ import annotations

import asyncio
import os

import httpx
from demo_common import assert_status, auth_headers, bootstrap_admin, wait_ok


async def _run() -> None:
    base_url = os.getenv("APP_BASE_URL", "http://app:8000").rstrip("/")
    timeout = httpx.Timeout(20.0)
    async with httpx.AsyncClient(base_url=base_url, timeout=timeout) as client:
        await wait_ok(client, "/healthz")
        await wait_ok(client, "/readyz")

        _tenant_id, token = await bootstrap_admin(client, "phase9")

        drone_resp = await client.post(
            "/api/registry/drones",
            json={"name": "phase9-drone", "vendor": "FAKE", "capabilities": {"camera": True}},
            headers=auth_headers(token),
        )
        assert_status(drone_resp, 201)
        drone_id = drone_resp.json()["id"]

        asset_a_resp = await client.post(
            "/api/assets",
            json={"asset_type": "UAV", "asset_code": "P9-UAV-01", "name": "uav-01"},
            headers=auth_headers(token),
        )
        assert_status(asset_a_resp, 201)
        asset_a_id = asset_a_resp.json()["id"]

        asset_b_resp = await client.post(
            "/api/assets",
            json={"asset_type": "BATTERY", "asset_code": "P9-BAT-01", "name": "bat-01"},
            headers=auth_headers(token),
        )
        assert_status(asset_b_resp, 201)
        asset_b_id = asset_b_resp.json()["id"]

        bind_resp = await client.post(
            f"/api/assets/{asset_a_id}/bind",
            json={"bound_to_drone_id": drone_id},
            headers=auth_headers(token),
        )
        assert_status(bind_resp, 200)

        avail_a_resp = await client.post(
            f"/api/assets/{asset_a_id}/availability",
            json={"availability_status": "AVAILABLE", "region_code": "REGION-EAST"},
            headers=auth_headers(token),
        )
        assert_status(avail_a_resp, 200)

        health_a_resp = await client.post(
            f"/api/assets/{asset_a_id}/health",
            json={"health_status": "HEALTHY", "health_score": 95},
            headers=auth_headers(token),
        )
        assert_status(health_a_resp, 200)

        avail_b_resp = await client.post(
            f"/api/assets/{asset_b_id}/availability",
            json={"availability_status": "MAINTENANCE", "region_code": "REGION-EAST"},
            headers=auth_headers(token),
        )
        assert_status(avail_b_resp, 200)

        health_b_resp = await client.post(
            f"/api/assets/{asset_b_id}/health",
            json={"health_status": "DEGRADED", "health_score": 60},
            headers=auth_headers(token),
        )
        assert_status(health_b_resp, 200)

        wo_create_resp = await client.post(
            "/api/assets/maintenance/workorders",
            json={
                "asset_id": asset_b_id,
                "title": "replace battery cells",
                "priority": 3,
                "note": "phase9 demo create",
            },
            headers=auth_headers(token),
        )
        assert_status(wo_create_resp, 201)
        workorder_id = wo_create_resp.json()["id"]

        wo_transition_resp = await client.post(
            f"/api/assets/maintenance/workorders/{workorder_id}/transition",
            json={"status": "IN_PROGRESS", "note": "phase9 demo transition"},
            headers=auth_headers(token),
        )
        assert_status(wo_transition_resp, 200)

        wo_close_resp = await client.post(
            f"/api/assets/maintenance/workorders/{workorder_id}/close",
            json={"note": "phase9 demo close"},
            headers=auth_headers(token),
        )
        assert_status(wo_close_resp, 200)

        history_resp = await client.get(
            f"/api/assets/maintenance/workorders/{workorder_id}/history",
            headers=auth_headers(token),
        )
        assert_status(history_resp, 200)
        actions = [item["action"] for item in history_resp.json()]
        if actions != ["created", "status_changed", "closed"]:
            raise RuntimeError(f"unexpected maintenance history actions: {actions}")

        pool_resp = await client.get(
            "/api/assets/pool",
            params={"region_code": "REGION-EAST", "availability_status": "AVAILABLE"},
            headers=auth_headers(token),
        )
        assert_status(pool_resp, 200)
        pool_ids = {item["id"] for item in pool_resp.json()}
        if asset_a_id not in pool_ids:
            raise RuntimeError("resource pool missing expected available asset")

        summary_resp = await client.get(
            "/api/assets/pool/summary",
            params={"region_code": "REGION-EAST"},
            headers=auth_headers(token),
        )
        assert_status(summary_resp, 200)
        summary = summary_resp.json()
        if not summary or summary[0]["region_code"] != "REGION-EAST":
            raise RuntimeError(f"unexpected pool summary payload: {summary}")

    print("demo_phase09_resource_pool_maintenance: ok")


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
