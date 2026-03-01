from __future__ import annotations

import asyncio
import os

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

        _tenant_id, token = await bootstrap_admin(client, "phase27")
        operator_id = await _create_user(client, token, "phase27-operator", "phase27-pass")

        inspection_template_id = await create_template(client, token, name="phase27-inspection")
        inspection_task_id = await create_inspection_task(
            client,
            token,
            inspection_template_id,
            name="phase27-inspection-task",
        )
        observation_id = await add_observation(
            client,
            token,
            inspection_task_id,
            item_code="SIDEWALK_OCCUPY",
            lat=30.5928,
            lon=114.3055,
            severity=3,
            note="phase27 observation",
        )

        defect_resp = await client.post(
            f"/api/defects/from-observation/{observation_id}",
            headers=auth_headers(token),
        )
        assert_status(defect_resp, 201)
        defect_id = defect_resp.json()["id"]

        defect_assign_resp = await client.post(
            f"/api/defects/{defect_id}/assign",
            json={"assigned_to": operator_id, "note": "phase27 assign"},
            headers=auth_headers(token),
        )
        assert_status(defect_assign_resp, 200)

        defect_status_resp = await client.post(
            f"/api/defects/{defect_id}/status",
            json={"status": "IN_PROGRESS", "note": "phase27 status"},
            headers=auth_headers(token),
        )
        assert_status(defect_status_resp, 200)

        defect_detail_resp = await client.get(f"/api/defects/{defect_id}", headers=auth_headers(token))
        assert_status(defect_detail_resp, 200)
        if defect_detail_resp.json()["defect"]["observation_id"] != observation_id:
            raise RuntimeError("phase27 demo expected defect linked to observation")

        incident_resp = await client.post(
            "/api/incidents",
            json={
                "title": "phase27 emergency",
                "level": "HIGH",
                "location_geom": "POINT(114.305500 30.592800)",
            },
            headers=auth_headers(token),
        )
        assert_status(incident_resp, 201)
        incident_id = incident_resp.json()["id"]

        incident_task_resp = await client.post(
            f"/api/incidents/{incident_id}/create-task",
            json={"template_id": inspection_template_id, "task_name": "phase27 emergency task"},
            headers=auth_headers(token),
        )
        assert_status(incident_task_resp, 200)
        emergency_task_id = incident_task_resp.json()["task_id"]

        task_type_resp = await client.post(
            "/api/task-center/types",
            json={"code": "PH27-OPS", "name": "phase27-ops", "description": "phase27 ops flow"},
            headers=auth_headers(token),
        )
        assert_status(task_type_resp, 201)
        task_type_id = task_type_resp.json()["id"]

        task_template_resp = await client.post(
            "/api/task-center/templates",
            json={
                "task_type_id": task_type_id,
                "template_key": "phase27-template",
                "name": "phase27-template",
                "requires_approval": True,
                "default_priority": 6,
                "default_risk_level": 3,
                "default_checklist": [{"code": "C1", "title": "pre-check"}],
            },
            headers=auth_headers(token),
        )
        assert_status(task_template_resp, 201)
        task_template_id = task_template_resp.json()["id"]

        task_resp = await client.post(
            "/api/task-center/tasks",
            json={
                "task_type_id": task_type_id,
                "template_id": task_template_id,
                "name": "phase27-main-task",
                "project_code": "PH27",
                "area_code": "AREA-PH27",
            },
            headers=auth_headers(token),
        )
        assert_status(task_resp, 201)
        task_id = task_resp.json()["id"]

        submit_resp = await client.post(
            f"/api/task-center/tasks/{task_id}/submit-approval",
            json={"note": "phase27 submit"},
            headers=auth_headers(token),
        )
        assert_status(submit_resp, 200)

        approve_resp = await client.post(
            f"/api/task-center/tasks/{task_id}/approve",
            json={"decision": "APPROVE", "note": "phase27 approve"},
            headers=auth_headers(token),
        )
        assert_status(approve_resp, 200)

        dispatch_resp = await client.post(
            f"/api/task-center/tasks/{task_id}/dispatch",
            json={"assigned_to": operator_id, "note": "phase27 dispatch"},
            headers=auth_headers(token),
        )
        assert_status(dispatch_resp, 200)

        transition_resp = await client.post(
            f"/api/task-center/tasks/{task_id}/transition",
            json={"target_state": "IN_PROGRESS"},
            headers=auth_headers(token),
        )
        assert_status(transition_resp, 200)

        comment_resp = await client.post(
            f"/api/task-center/tasks/{task_id}/comments",
            json={"content": "phase27 comment"},
            headers=auth_headers(token),
        )
        assert_status(comment_resp, 200)

        history_resp = await client.get(f"/api/task-center/tasks/{task_id}/history", headers=auth_headers(token))
        assert_status(history_resp, 200)
        if len(history_resp.json()) < 3:
            raise RuntimeError("phase27 demo expected task history events")

        batch_resp = await client.post(
            "/api/task-center/tasks:batch-create",
            json={
                "tasks": [
                    {
                        "task_type_id": task_type_id,
                        "template_id": task_template_id,
                        "name": "phase27-batch-a",
                    },
                    {
                        "task_type_id": task_type_id,
                        "template_id": task_template_id,
                        "name": "phase27-batch-b",
                    },
                ]
            },
            headers=auth_headers(token),
        )
        assert_status(batch_resp, 201)
        if batch_resp.json()["total"] != 2:
            raise RuntimeError("phase27 demo expected two batch-created tasks")

        asset_resp = await client.post(
            "/api/assets",
            json={"asset_type": "UAV", "asset_code": "PH27-UAV-01", "name": "phase27-uav"},
            headers=auth_headers(token),
        )
        assert_status(asset_resp, 201)
        asset_id = asset_resp.json()["id"]

        availability_resp = await client.post(
            f"/api/assets/{asset_id}/availability",
            json={"availability_status": "AVAILABLE", "region_code": "PH27-REGION"},
            headers=auth_headers(token),
        )
        assert_status(availability_resp, 200)

        health_resp = await client.post(
            f"/api/assets/{asset_id}/health",
            json={"health_status": "HEALTHY", "health_score": 95},
            headers=auth_headers(token),
        )
        assert_status(health_resp, 200)

        workorder_resp = await client.post(
            "/api/assets/maintenance/workorders",
            json={"asset_id": asset_id, "title": "phase27 maintenance", "priority": 4, "assigned_to": operator_id},
            headers=auth_headers(token),
        )
        assert_status(workorder_resp, 201)
        workorder_id = workorder_resp.json()["id"]

        workorder_transition = await client.post(
            f"/api/assets/maintenance/workorders/{workorder_id}/transition",
            json={"status": "IN_PROGRESS", "assigned_to": operator_id, "note": "phase27 start"},
            headers=auth_headers(token),
        )
        assert_status(workorder_transition, 200)

        workorder_history = await client.get(
            f"/api/assets/maintenance/workorders/{workorder_id}/history",
            headers=auth_headers(token),
        )
        assert_status(workorder_history, 200)
        if len(workorder_history.json()) < 2:
            raise RuntimeError("phase27 demo expected maintenance workorder history")

        workorder_close = await client.post(
            f"/api/assets/maintenance/workorders/{workorder_id}/close",
            json={"note": "phase27 done"},
            headers=auth_headers(token),
        )
        assert_status(workorder_close, 200)

        ui_checks = [
            ("/ui/task-center", "Batch Create Tasks"),
            ("/ui/assets", "Maintenance Workorders"),
            ("/ui/inspection", "Create Inspection Task"),
            (f"/ui/inspection/tasks/{inspection_task_id}", "Create Defect From Observation"),
            ("/ui/defects", "Load Detail"),
            ("/ui/emergency", "Recent Incidents"),
        ]
        for path, expected_text in ui_checks:
            response = await client.get(f"{path}?token={token}")
            assert_status(response, 200)
            if expected_text not in response.text:
                raise RuntimeError(f"phase27 demo expected '{expected_text}' in {path}")

        incidents_resp = await client.get("/api/incidents", headers=auth_headers(token))
        assert_status(incidents_resp, 200)
        incidents = incidents_resp.json()
        if not any(item.get("linked_task_id") == emergency_task_id for item in incidents):
            raise RuntimeError("phase27 demo expected incident-linked task to be queryable")

    print("demo_phase27_operations_ui_closure: ok")


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
