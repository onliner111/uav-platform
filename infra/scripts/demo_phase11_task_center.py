from __future__ import annotations

import asyncio
import os

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

        _tenant_id, token = await bootstrap_admin(client, "phase11")

        org_resp = await client.post(
            "/api/identity/org-units",
            json={"name": "phase11-ops", "code": "PH11-OPS", "is_active": True},
            headers=auth_headers(token),
        )
        assert_status(org_resp, 201)
        org_unit_id = org_resp.json()["id"]

        user_a_id = await _create_user(client, token, "phase11-user-a", "phase11-pass-a")
        user_b_id = await _create_user(client, token, "phase11-user-b", "phase11-pass-b")

        bind_org_resp = await client.post(
            f"/api/identity/users/{user_a_id}/org-units/{org_unit_id}",
            json={"is_primary": True},
            headers=auth_headers(token),
        )
        assert_status(bind_org_resp, 200)

        asset_resp = await client.post(
            "/api/assets",
            json={"asset_type": "UAV", "asset_code": "PH11-UAV-01", "name": "phase11-uav"},
            headers=auth_headers(token),
        )
        assert_status(asset_resp, 201)
        asset_id = asset_resp.json()["id"]

        avail_resp = await client.post(
            f"/api/assets/{asset_id}/availability",
            json={"availability_status": "AVAILABLE", "region_code": "AREA-DEMO"},
            headers=auth_headers(token),
        )
        assert_status(avail_resp, 200)

        type_resp = await client.post(
            "/api/task-center/types",
            json={"code": "PH11-INSPECT", "name": "phase11-inspect", "description": "phase11 demo type"},
            headers=auth_headers(token),
        )
        assert_status(type_resp, 201)
        task_type_id = type_resp.json()["id"]

        template_resp = await client.post(
            "/api/task-center/templates",
            json={
                "task_type_id": task_type_id,
                "template_key": "phase11-template-a",
                "name": "phase11-template",
                "requires_approval": True,
                "default_priority": 4,
                "default_risk_level": 2,
                "default_checklist": [{"code": "CHK-1", "title": "initial check"}],
            },
            headers=auth_headers(token),
        )
        assert_status(template_resp, 201)
        template_id = template_resp.json()["id"]

        manual_task_resp = await client.post(
            "/api/task-center/tasks",
            json={
                "task_type_id": task_type_id,
                "template_id": template_id,
                "name": "phase11-manual-task",
                "org_unit_id": org_unit_id,
                "area_code": "AREA-DEMO",
            },
            headers=auth_headers(token),
        )
        assert_status(manual_task_resp, 201)
        manual_task_id = manual_task_resp.json()["id"]

        submit_resp = await client.post(
            f"/api/task-center/tasks/{manual_task_id}/submit-approval",
            json={"note": "phase11 submit"},
            headers=auth_headers(token),
        )
        assert_status(submit_resp, 200)

        approve_resp = await client.post(
            f"/api/task-center/tasks/{manual_task_id}/approve",
            json={"decision": "APPROVE", "note": "phase11 approve"},
            headers=auth_headers(token),
        )
        assert_status(approve_resp, 200)

        dispatch_resp = await client.post(
            f"/api/task-center/tasks/{manual_task_id}/dispatch",
            json={"assigned_to": user_a_id, "note": "manual dispatch"},
            headers=auth_headers(token),
        )
        assert_status(dispatch_resp, 200)

        for state_name in ("IN_PROGRESS", "ACCEPTED", "ARCHIVED"):
            transition_resp = await client.post(
                f"/api/task-center/tasks/{manual_task_id}/transition",
                json={"target_state": state_name},
                headers=auth_headers(token),
            )
            assert_status(transition_resp, 200)

        auto_task_resp = await client.post(
            "/api/task-center/tasks",
            json={
                "task_type_id": task_type_id,
                "name": "phase11-auto-task",
                "org_unit_id": org_unit_id,
                "area_code": "AREA-DEMO",
                "requires_approval": False,
                "risk_level": 2,
                "checklist": [{"code": "AUTO-1", "title": "auto check"}],
            },
            headers=auth_headers(token),
        )
        assert_status(auto_task_resp, 201)
        auto_task_id = auto_task_resp.json()["id"]

        auto_dispatch_resp = await client.post(
            f"/api/task-center/tasks/{auto_task_id}/auto-dispatch",
            json={"candidate_user_ids": [user_b_id, user_a_id], "note": "auto dispatch"},
            headers=auth_headers(token),
        )
        assert_status(auto_dispatch_resp, 200)
        auto_payload = auto_dispatch_resp.json()
        if auto_payload["task"]["dispatch_mode"] != "AUTO":
            raise RuntimeError(f"unexpected auto dispatch payload: {auto_payload}")
        if len(auto_payload.get("scores", [])) < 2:
            raise RuntimeError(f"missing score explanation payload: {auto_payload}")

        risk_resp = await client.patch(
            f"/api/task-center/tasks/{auto_task_id}/risk-checklist",
            json={
                "risk_level": 5,
                "checklist": [
                    {"code": "AUTO-1", "title": "auto check", "status": "DONE"},
                    {"code": "AUTO-2", "title": "closure check", "status": "PENDING"},
                ],
                "note": "risk adjusted",
            },
            headers=auth_headers(token),
        )
        assert_status(risk_resp, 200)

        attachment_resp = await client.post(
            f"/api/task-center/tasks/{auto_task_id}/attachments",
            json={"name": "phase11-photo", "url": "https://example.com/phase11.jpg", "media_type": "image/jpeg"},
            headers=auth_headers(token),
        )
        assert_status(attachment_resp, 200)

        comment_resp = await client.post(
            f"/api/task-center/tasks/{auto_task_id}/comments",
            json={"content": "phase11 comment"},
            headers=auth_headers(token),
        )
        assert_status(comment_resp, 200)

        comments_resp = await client.get(
            f"/api/task-center/tasks/{auto_task_id}/comments",
            headers=auth_headers(token),
        )
        assert_status(comments_resp, 200)
        if len(comments_resp.json()) < 1:
            raise RuntimeError("comments should not be empty")

        history_resp = await client.get(
            f"/api/task-center/tasks/{auto_task_id}/history",
            headers=auth_headers(token),
        )
        assert_status(history_resp, 200)
        actions = {item["action"] for item in history_resp.json()}
        required_actions = {"created", "dispatched", "risk_checklist_updated", "attachment_added", "comment_added"}
        if not required_actions.issubset(actions):
            raise RuntimeError(f"history missing required actions: actions={actions}")

    print("demo_phase11_task_center: ok")


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
