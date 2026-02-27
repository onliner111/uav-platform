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

        _tenant_id, token = await bootstrap_admin(client, "phase21")

        org_resp = await client.post(
            "/api/identity/org-units",
            json={"name": "phase21-ops", "code": "P21-OPS", "node_type": "ORGANIZATION"},
            headers=auth_headers(token),
        )
        assert_status(org_resp, 201)
        org_unit_id = org_resp.json()["id"]

        deny_zone_resp = await client.post(
            "/api/compliance/zones",
            json={
                "name": "phase21-tenant-no-fly",
                "zone_type": "NO_FLY",
                "policy_layer": "TENANT",
                "policy_effect": "DENY",
                "geom_wkt": "POLYGON((114.19 30.09,114.21 30.09,114.21 30.11,114.19 30.11,114.19 30.09))",
            },
            headers=auth_headers(token),
        )
        assert_status(deny_zone_resp, 201)

        allow_zone_resp = await client.post(
            "/api/compliance/zones",
            json={
                "name": "phase21-org-allow",
                "zone_type": "NO_FLY",
                "policy_layer": "ORG_UNIT",
                "policy_effect": "ALLOW",
                "org_unit_id": org_unit_id,
                "geom_wkt": "POLYGON((114.19 30.09,114.21 30.09,114.21 30.11,114.19 30.11,114.19 30.09))",
            },
            headers=auth_headers(token),
        )
        assert_status(allow_zone_resp, 201)

        mission_resp = await client.post(
            "/api/mission/missions",
            json={
                "name": "phase21-mission",
                "type": "POINT_TASK",
                "org_unit_id": org_unit_id,
                "payload": {"point": {"lat": 30.1, "lon": 114.2, "alt_m": 100}},
                "constraints": {},
            },
            headers=auth_headers(token),
        )
        assert_status(mission_resp, 201)
        mission_id = mission_resp.json()["id"]

        drone_resp = await client.post(
            "/api/registry/drones",
            json={"name": "phase21-drone", "vendor": "FAKE", "capabilities": {"rth": True}},
            headers=auth_headers(token),
        )
        assert_status(drone_resp, 201)
        drone_id = drone_resp.json()["id"]

        flow_template_resp = await client.post(
            "/api/compliance/approval-flows/templates",
            json={
                "name": "phase21-mission-flow",
                "entity_type": "MISSION",
                "steps": [{"name": "L1"}, {"name": "L2"}],
            },
            headers=auth_headers(token),
        )
        assert_status(flow_template_resp, 201)
        flow_template_id = flow_template_resp.json()["id"]

        flow_instance_resp = await client.post(
            "/api/compliance/approval-flows/instances",
            json={
                "template_id": flow_template_id,
                "entity_type": "MISSION",
                "entity_id": mission_id,
            },
            headers=auth_headers(token),
        )
        assert_status(flow_instance_resp, 201)
        flow_instance_id = flow_instance_resp.json()["id"]

        start_blocked_resp = await client.post(
            "/api/command/commands",
            json={
                "drone_id": drone_id,
                "type": "START_MISSION",
                "params": {"mission_id": mission_id},
                "idempotency_key": "phase21-demo-start-blocked",
                "expect_ack": True,
            },
            headers=auth_headers(token),
        )
        assert_status(start_blocked_resp, 409)

        for _ in range(2):
            act_resp = await client.post(
                f"/api/compliance/approval-flows/instances/{flow_instance_id}/actions",
                json={"action": "APPROVE"},
                headers=auth_headers(token),
            )
            assert_status(act_resp, 200)

        preflight_template_resp = await client.post(
            "/api/compliance/preflight/templates",
            json={
                "name": "phase21-preflight-template",
                "items": [{"code": "CHK-E", "title": "evidence required"}],
                "template_version": "v2",
                "evidence_requirements": {"required": True},
                "require_approval_before_run": True,
            },
            headers=auth_headers(token),
        )
        assert_status(preflight_template_resp, 201)
        preflight_template_id = preflight_template_resp.json()["id"]

        init_resp = await client.post(
            f"/api/compliance/missions/{mission_id}/preflight/init",
            json={"template_id": preflight_template_id},
            headers=auth_headers(token),
        )
        assert_status(init_resp, 200)

        check_resp = await client.post(
            f"/api/compliance/missions/{mission_id}/preflight/check-item",
            json={
                "item_code": "CHK-E",
                "checked": True,
                "evidence": {"photo_url": "https://example.invalid/p21.jpg"},
            },
            headers=auth_headers(token),
        )
        assert_status(check_resp, 200)

        start_ok_resp = await client.post(
            "/api/command/commands",
            json={
                "drone_id": drone_id,
                "type": "START_MISSION",
                "params": {"mission_id": mission_id},
                "idempotency_key": "phase21-demo-start-ok",
                "expect_ack": True,
            },
            headers=auth_headers(token),
        )
        assert_status(start_ok_resp, 201)

        task_type_resp = await client.post(
            "/api/task-center/types",
            json={"code": "P21", "name": "phase21"},
            headers=auth_headers(token),
        )
        assert_status(task_type_resp, 201)
        task_type_id = task_type_resp.json()["id"]

        task_resp = await client.post(
            "/api/task-center/tasks",
            json={
                "task_type_id": task_type_id,
                "mission_id": mission_id,
                "org_unit_id": org_unit_id,
                "name": "phase21-task",
            },
            headers=auth_headers(token),
        )
        assert_status(task_resp, 201)
        snapshot = task_resp.json()["context_data"].get("compliance_snapshot", {})
        if snapshot.get("mission_id") != mission_id:
            raise RuntimeError("compliance snapshot not linked to mission")

        export_resp = await client.get(
            "/api/compliance/decision-records/export?entity_type=MISSION&entity_id=" + mission_id,
            headers=auth_headers(token),
        )
        assert_status(export_resp, 200)
        if "file_path" not in export_resp.json():
            raise RuntimeError("decision export file path missing")

    print("demo_phase21_airspace_compliance_hub_v2: ok")


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
