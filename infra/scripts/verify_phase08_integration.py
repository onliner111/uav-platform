from __future__ import annotations

import asyncio
import os
import time
from typing import Any
from uuid import uuid4

import httpx
from sqlmodel import Session, select

from app.domain.models import AuditLog
from app.infra.db import get_engine


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


def _load_audit_entries(tenant_id: str) -> list[dict[str, Any]]:
    with Session(get_engine(), expire_on_commit=False) as session:
        rows = list(session.exec(select(AuditLog).where(AuditLog.tenant_id == tenant_id)).all())
    return [
        {
            "id": item.id,
            "action": item.action,
            "resource": item.resource,
            "method": item.method,
            "status_code": item.status_code,
            "ts": item.ts.isoformat(),
            "actor_id": item.actor_id,
            "detail": item.detail,
        }
        for item in rows
    ]


def _find_log(
    entries: list[dict[str, Any]],
    *,
    action: str,
    status_code: int | None = None,
) -> dict[str, Any]:
    matched = [item for item in entries if item.get("action") == action]
    if status_code is not None:
        matched = [item for item in matched if item.get("status_code") == status_code]
    if not matched:
        raise RuntimeError(f"audit log not found: action={action}, status_code={status_code}")
    matched.sort(key=lambda item: str(item.get("ts", "")))
    return matched[-1]


async def _run() -> None:
    base_url = os.getenv("APP_BASE_URL", "http://app:8000").rstrip("/")
    run_id = uuid4().hex[:8]
    timeout = httpx.Timeout(20.0)

    async with httpx.AsyncClient(base_url=base_url, timeout=timeout) as client:
        await _wait_ok(client, "/healthz")
        await _wait_ok(client, "/readyz")

        tenant_a_name = f"phase08d-a-{run_id}"
        tenant_b_name = f"phase08d-b-{run_id}"

        tenant_a_resp = await client.post("/api/identity/tenants", json={"name": tenant_a_name})
        _assert_status(tenant_a_resp, 201)
        tenant_a_id = tenant_a_resp.json()["id"]

        tenant_b_resp = await client.post("/api/identity/tenants", json={"name": tenant_b_name})
        _assert_status(tenant_b_resp, 201)
        tenant_b_id = tenant_b_resp.json()["id"]

        admin_a_name = f"admin-a-{run_id}"
        admin_b_name = f"admin-b-{run_id}"
        password = f"pass-{run_id}"

        bootstrap_a_resp = await client.post(
            "/api/identity/bootstrap-admin",
            json={"tenant_id": tenant_a_id, "username": admin_a_name, "password": password},
        )
        _assert_status(bootstrap_a_resp, 201)
        bootstrap_b_resp = await client.post(
            "/api/identity/bootstrap-admin",
            json={"tenant_id": tenant_b_id, "username": admin_b_name, "password": password},
        )
        _assert_status(bootstrap_b_resp, 201)

        admin_a_login = await client.post(
            "/api/identity/dev-login",
            json={"tenant_id": tenant_a_id, "username": admin_a_name, "password": password},
        )
        _assert_status(admin_a_login, 200)
        admin_a_token = admin_a_login.json()["access_token"]

        admin_b_login = await client.post(
            "/api/identity/dev-login",
            json={"tenant_id": tenant_b_id, "username": admin_b_name, "password": password},
        )
        _assert_status(admin_b_login, 200)
        admin_b_token = admin_b_login.json()["access_token"]

        operator_resp = await client.post(
            "/api/identity/users",
            json={"username": f"operator-{run_id}", "password": password, "is_active": True},
            headers=_auth_headers(admin_a_token),
        )
        _assert_status(operator_resp, 201)
        operator_id = operator_resp.json()["id"]

        viewer_resp = await client.post(
            "/api/identity/users",
            json={"username": f"viewer-{run_id}", "password": password, "is_active": True},
            headers=_auth_headers(admin_a_token),
        )
        _assert_status(viewer_resp, 201)
        viewer_id = viewer_resp.json()["id"]

        dispatcher_role_resp = await client.post(
            "/api/identity/roles:from-template",
            json={"template_key": "dispatcher", "name": f"dispatcher-{run_id}"},
            headers=_auth_headers(admin_a_token),
        )
        _assert_status(dispatcher_role_resp, 201)
        dispatcher_role_id = dispatcher_role_resp.json()["id"]

        viewer_role_resp = await client.post(
            "/api/identity/roles",
            json={"name": f"viewer-role-{run_id}", "description": "no mission permissions"},
            headers=_auth_headers(admin_a_token),
        )
        _assert_status(viewer_role_resp, 201)
        viewer_role_id = viewer_role_resp.json()["id"]

        batch_bind_resp = await client.post(
            f"/api/identity/users/{operator_id}/roles:batch-bind",
            json={"role_ids": [dispatcher_role_id]},
            headers=_auth_headers(admin_a_token),
        )
        _assert_status(batch_bind_resp, 200)
        batch_bind_body = batch_bind_resp.json()
        if batch_bind_body["bound_count"] != 1 or batch_bind_body["denied_count"] != 0:
            raise RuntimeError(f"unexpected batch bind result: {batch_bind_body}")

        viewer_bind_resp = await client.post(
            f"/api/identity/users/{viewer_id}/roles/{viewer_role_id}",
            headers=_auth_headers(admin_a_token),
        )
        _assert_status(viewer_bind_resp, 204)

        policy_resp = await client.put(
            f"/api/identity/users/{operator_id}/data-policy",
            json={
                "scope_mode": "SCOPED",
                "project_codes": ["PROJ-ALPHA"],
            },
            headers=_auth_headers(admin_a_token),
        )
        _assert_status(policy_resp, 200)

        alpha_mission_resp = await client.post(
            "/api/mission/missions",
            json={
                "name": f"mission-alpha-{run_id}",
                "type": "ROUTE_WAYPOINTS",
                "project_code": "PROJ-ALPHA",
                "payload": {"waypoints": []},
                "constraints": {},
            },
            headers=_auth_headers(admin_a_token),
        )
        _assert_status(alpha_mission_resp, 201)
        alpha_mission_id = alpha_mission_resp.json()["id"]

        beta_mission_resp = await client.post(
            "/api/mission/missions",
            json={
                "name": f"mission-beta-{run_id}",
                "type": "ROUTE_WAYPOINTS",
                "project_code": "PROJ-BETA",
                "payload": {"waypoints": []},
                "constraints": {},
            },
            headers=_auth_headers(admin_a_token),
        )
        _assert_status(beta_mission_resp, 201)
        beta_mission_id = beta_mission_resp.json()["id"]

        operator_login_resp = await client.post(
            "/api/identity/dev-login",
            json={"tenant_id": tenant_a_id, "username": f"operator-{run_id}", "password": password},
        )
        _assert_status(operator_login_resp, 200)
        operator_token = operator_login_resp.json()["access_token"]

        viewer_login_resp = await client.post(
            "/api/identity/dev-login",
            json={"tenant_id": tenant_a_id, "username": f"viewer-{run_id}", "password": password},
        )
        _assert_status(viewer_login_resp, 200)
        viewer_token = viewer_login_resp.json()["access_token"]

        operator_list_resp = await client.get(
            "/api/mission/missions",
            headers=_auth_headers(operator_token),
        )
        _assert_status(operator_list_resp, 200)
        operator_mission_ids = {item["id"] for item in operator_list_resp.json()}
        if alpha_mission_id not in operator_mission_ids or beta_mission_id in operator_mission_ids:
            raise RuntimeError(
                f"data perimeter not enforced for operator: alpha={alpha_mission_id}, beta={beta_mission_id}, "
                f"seen={operator_mission_ids}"
            )

        viewer_list_resp = await client.get(
            "/api/mission/missions",
            headers=_auth_headers(viewer_token),
        )
        _assert_status(viewer_list_resp, 403)

        cross_tenant_get_resp = await client.get(
            f"/api/identity/users/{operator_id}/data-policy",
            headers=_auth_headers(admin_b_token),
        )
        _assert_status(cross_tenant_get_resp, 404)

        tenant_a_audit_export_resp = await client.get(
            "/api/approvals/audit-export",
            headers=_auth_headers(admin_a_token),
        )
        _assert_status(tenant_a_audit_export_resp, 200)
        if not tenant_a_audit_export_resp.json().get("file_path"):
            raise RuntimeError("tenant A audit export did not return file_path")
        tenant_a_entries = _load_audit_entries(tenant_a_id)

        _find_log(tenant_a_entries, action="identity.data_policy.upsert", status_code=200)
        _find_log(tenant_a_entries, action="identity.user_role.batch_bind", status_code=200)
        _find_log(tenant_a_entries, action="GET:/api/approvals/audit-export", status_code=200)

        tenant_b_audit_export_resp = await client.get(
            "/api/approvals/audit-export",
            headers=_auth_headers(admin_b_token),
        )
        _assert_status(tenant_b_audit_export_resp, 200)
        if not tenant_b_audit_export_resp.json().get("file_path"):
            raise RuntimeError("tenant B audit export did not return file_path")
        tenant_b_entries = _load_audit_entries(tenant_b_id)
        deny_log = _find_log(tenant_b_entries, action="identity.data_policy.get", status_code=404)
        deny_detail = deny_log.get("detail", {})
        result = deny_detail.get("result", {}) if isinstance(deny_detail, dict) else {}
        if result.get("reason") != "cross_tenant_boundary":
            raise RuntimeError(f"unexpected cross-tenant deny audit detail: {deny_log}")

    print("verify_phase08_integration: multi-role/perimeter/audit chain ok")


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
