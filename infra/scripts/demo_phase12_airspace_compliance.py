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

        _tenant_id, token = await bootstrap_admin(client, "phase12")

        drone_resp = await client.post(
            "/api/registry/drones",
            json={"name": "phase12-drone", "vendor": "FAKE", "capabilities": {"rth": True}},
            headers=auth_headers(token),
        )
        assert_status(drone_resp, 201)
        drone_id = drone_resp.json()["id"]

        zone_resp = await client.post(
            "/api/compliance/zones",
            json={
                "name": "phase12-no-fly",
                "zone_type": "NO_FLY",
                "geom_wkt": "POLYGON((114.19 30.09,114.21 30.09,114.21 30.11,114.19 30.11,114.19 30.09))",
            },
            headers=auth_headers(token),
        )
        assert_status(zone_resp, 201)

        blocked_mission_resp = await client.post(
            "/api/mission/missions",
            json={
                "name": "phase12-blocked-mission",
                "type": "POINT_TASK",
                "payload": {"point": {"lat": 30.1, "lon": 114.2, "alt_m": 100}},
                "constraints": {},
            },
            headers=auth_headers(token),
        )
        assert_status(blocked_mission_resp, 409)
        if blocked_mission_resp.json()["detail"]["reason_code"] != "AIRSPACE_NO_FLY":
            raise RuntimeError(f"unexpected mission block reason: {blocked_mission_resp.text}")

        mission_resp = await client.post(
            "/api/mission/missions",
            json={
                "name": "phase12-legal-mission",
                "type": "POINT_TASK",
                "payload": {"point": {"lat": 30.15, "lon": 114.25, "alt_m": 100}},
                "constraints": {},
            },
            headers=auth_headers(token),
        )
        assert_status(mission_resp, 201)
        mission_id = mission_resp.json()["id"]

        approve_resp = await client.post(
            f"/api/mission/missions/{mission_id}/approve",
            json={"decision": "APPROVE", "comment": "phase12 approve"},
            headers=auth_headers(token),
        )
        assert_status(approve_resp, 200)

        run_before_preflight_resp = await client.post(
            f"/api/mission/missions/{mission_id}/transition",
            json={"target_state": "RUNNING"},
            headers=auth_headers(token),
        )
        assert_status(run_before_preflight_resp, 409)
        if run_before_preflight_resp.json()["detail"]["reason_code"] != "PREFLIGHT_CHECKLIST_REQUIRED":
            raise RuntimeError(f"unexpected preflight guard result: {run_before_preflight_resp.text}")

        template_resp = await client.post(
            "/api/compliance/preflight/templates",
            json={
                "name": "phase12-template",
                "items": [
                    {"code": "CHK-A", "title": "airframe"},
                    {"code": "CHK-B", "title": "battery"},
                ],
                "require_approval_before_run": True,
                "is_active": True,
            },
            headers=auth_headers(token),
        )
        assert_status(template_resp, 201)
        template_id = template_resp.json()["id"]

        init_resp = await client.post(
            f"/api/compliance/missions/{mission_id}/preflight/init",
            json={"template_id": template_id},
            headers=auth_headers(token),
        )
        assert_status(init_resp, 200)

        for item_code in ("CHK-A", "CHK-B"):
            check_resp = await client.post(
                f"/api/compliance/missions/{mission_id}/preflight/check-item",
                json={"item_code": item_code, "checked": True},
                headers=auth_headers(token),
            )
            assert_status(check_resp, 200)

        blocked_goto_resp = await client.post(
            "/api/command/commands",
            json={
                "drone_id": drone_id,
                "type": "GOTO",
                "params": {"lat": 30.1, "lon": 114.2, "alt_m": 80},
                "idempotency_key": "phase12-demo-goto-blocked",
                "expect_ack": True,
            },
            headers=auth_headers(token),
        )
        assert_status(blocked_goto_resp, 409)
        if blocked_goto_resp.json()["detail"]["reason_code"] != "COMMAND_GEOFENCE_BLOCKED":
            raise RuntimeError(f"unexpected command block reason: {blocked_goto_resp.text}")

        start_resp = await client.post(
            "/api/command/commands",
            json={
                "drone_id": drone_id,
                "type": "START_MISSION",
                "params": {"mission_id": mission_id},
                "idempotency_key": "phase12-demo-start-ok",
                "expect_ack": True,
            },
            headers=auth_headers(token),
        )
        assert_status(start_resp, 201)
        if start_resp.json()["status"] != "ACKED" or start_resp.json()["compliance_passed"] is not True:
            raise RuntimeError(f"unexpected start mission response: {start_resp.text}")

        run_ok_resp = await client.post(
            f"/api/mission/missions/{mission_id}/transition",
            json={"target_state": "RUNNING"},
            headers=auth_headers(token),
        )
        assert_status(run_ok_resp, 200)

    print("demo_phase12_airspace_compliance: ok")


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
