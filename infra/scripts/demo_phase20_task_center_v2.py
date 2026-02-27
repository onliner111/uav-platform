from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime, timedelta

import httpx
from demo_common import assert_status, auth_headers, bootstrap_admin, wait_ok


async def _create_user(client: httpx.AsyncClient, token: str, username: str, password: str) -> str:
    response = await client.post(
        "/api/identity/users",
        json={"username": username, "password": password, "is_active": True},
        headers=auth_headers(token),
    )
    assert_status(response, 201)
    return response.json()["id"]


async def _run() -> None:
    base_url = os.getenv("APP_BASE_URL", "http://app:8000").rstrip("/")
    timeout = httpx.Timeout(20.0)
    async with httpx.AsyncClient(base_url=base_url, timeout=timeout) as client:
        await wait_ok(client, "/healthz")
        await wait_ok(client, "/readyz")

        _tenant_id, token = await bootstrap_admin(client, "phase20")
        org_resp = await client.post(
            "/api/identity/org-units",
            json={"name": "phase20-ops", "code": "PH20-OPS", "is_active": True},
            headers=auth_headers(token),
        )
        assert_status(org_resp, 201)
        org_unit_id = org_resp.json()["id"]

        user_a_id = await _create_user(client, token, "phase20-user-a", "phase20-pass-a")
        user_b_id = await _create_user(client, token, "phase20-user-b", "phase20-pass-b")
        bind_org_resp = await client.post(
            f"/api/identity/users/{user_a_id}/org-units/{org_unit_id}",
            json={"is_primary": True},
            headers=auth_headers(token),
        )
        assert_status(bind_org_resp, 200)

        asset_resp = await client.post(
            "/api/assets",
            json={"asset_type": "UAV", "asset_code": "PH20-UAV-01", "name": "phase20-uav"},
            headers=auth_headers(token),
        )
        assert_status(asset_resp, 201)
        asset_id = asset_resp.json()["id"]
        avail_resp = await client.post(
            f"/api/assets/{asset_id}/availability",
            json={"availability_status": "AVAILABLE", "region_code": "AREA-PH20"},
            headers=auth_headers(token),
        )
        assert_status(avail_resp, 200)

        type_resp = await client.post(
            "/api/task-center/types",
            json={"code": "PH20-INSPECT", "name": "phase20-inspect"},
            headers=auth_headers(token),
        )
        assert_status(type_resp, 201)
        task_type_id = type_resp.json()["id"]

        template_resp = await client.post(
            "/api/task-center/templates",
            json={
                "task_type_id": task_type_id,
                "template_key": "phase20-template",
                "name": "phase20-template",
                "requires_approval": False,
                "default_priority": 6,
                "default_risk_level": 3,
                "route_template": {"mode": "grid", "waypoints": 16},
                "payload_template": {"camera": "4k", "sensor": "thermal"},
                "default_payload": {"biz_tag": "phase20"},
            },
            headers=auth_headers(token),
        )
        assert_status(template_resp, 201)
        template_id = template_resp.json()["id"]

        clone_resp = await client.post(
            f"/api/task-center/templates/{template_id}:clone",
            json={"template_key": "phase20-template-clone", "name": "phase20-template-clone"},
            headers=auth_headers(token),
        )
        assert_status(clone_resp, 201)

        base_start = datetime.now(UTC).replace(microsecond=0) + timedelta(hours=1)
        batch_resp = await client.post(
            "/api/task-center/tasks:batch-create",
            json={
                "tasks": [
                    {
                        "task_type_id": task_type_id,
                        "template_id": template_id,
                        "name": "phase20-task-a",
                        "org_unit_id": org_unit_id,
                        "area_code": "AREA-PH20",
                        "planned_start_at": base_start.isoformat(),
                        "planned_end_at": (base_start + timedelta(hours=2)).isoformat(),
                    },
                    {
                        "task_type_id": task_type_id,
                        "template_id": template_id,
                        "name": "phase20-task-b",
                        "org_unit_id": org_unit_id,
                        "area_code": "AREA-PH20",
                        "planned_start_at": (base_start + timedelta(minutes=30)).isoformat(),
                        "planned_end_at": (base_start + timedelta(hours=2, minutes=30)).isoformat(),
                    },
                ]
            },
            headers=auth_headers(token),
        )
        assert_status(batch_resp, 201)
        tasks = batch_resp.json()["tasks"]
        if len(tasks) != 2:
            raise RuntimeError("expected two batch tasks")
        task_a = tasks[0]["id"]
        task_b = tasks[1]["id"]

        dispatch_a = await client.post(
            f"/api/task-center/tasks/{task_a}/dispatch",
            json={"assigned_to": user_a_id},
            headers=auth_headers(token),
        )
        assert_status(dispatch_a, 200)

        dispatch_conflict = await client.post(
            f"/api/task-center/tasks/{task_b}/dispatch",
            json={"assigned_to": user_a_id},
            headers=auth_headers(token),
        )
        assert_status(dispatch_conflict, 409)

        auto_dispatch = await client.post(
            f"/api/task-center/tasks/{task_b}/auto-dispatch",
            json={"candidate_user_ids": [user_a_id, user_b_id]},
            headers=auth_headers(token),
        )
        assert_status(auto_dispatch, 200)
        auto_payload = auto_dispatch.json()
        if auto_payload["selected_user_id"] != user_b_id:
            raise RuntimeError(f"unexpected auto-dispatch selected user: {auto_payload}")
        if auto_payload["resource_snapshot"]["score_strategy"]["version"] != "v2.0":
            raise RuntimeError(f"unexpected score strategy payload: {auto_payload}")

    print("demo_phase20_task_center_v2: ok")


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
