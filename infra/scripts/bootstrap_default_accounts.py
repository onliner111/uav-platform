from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path
from uuid import uuid4

import httpx


def _env(name: str, default: str) -> str:
    return os.getenv(name, default).strip()


def _assert_status(response: httpx.Response, expected: int | tuple[int, ...]) -> None:
    expected_codes = (expected,) if isinstance(expected, int) else expected
    if response.status_code not in expected_codes:
        raise RuntimeError(
            f"{response.request.method} {response.request.url} expected {expected_codes}, "
            f"got {response.status_code}: {response.text}"
        )


async def _wait_ok(client: httpx.AsyncClient, path: str, timeout_seconds: float = 90.0) -> None:
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


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _create_tenant(client: httpx.AsyncClient, tenant_name: str) -> tuple[str, str]:
    response = await client.post("/api/identity/tenants", json={"name": tenant_name})
    if response.status_code == 201:
        body = response.json()
        return body["id"], body["name"]

    # If the default name already exists, append a small suffix and retry once.
    if response.status_code in (400, 409):
        fallback_name = f"{tenant_name}-{uuid4().hex[:6]}"
        retry = await client.post("/api/identity/tenants", json={"name": fallback_name})
        _assert_status(retry, 201)
        body = retry.json()
        return body["id"], body["name"]

    _assert_status(response, 201)
    raise RuntimeError("unreachable")


async def _run() -> None:
    base_url = _env("APP_BASE_URL", "http://app:8000").rstrip("/")
    tenant_name = _env("DEFAULT_TENANT_NAME", "default-demo")

    admin_username = _env("DEFAULT_ADMIN_USERNAME", "admin")
    admin_password = _env("DEFAULT_ADMIN_PASSWORD", "Admin@12345")

    role_accounts: list[dict[str, str]] = [
        {
            "role_key": "dispatcher",
            "username": _env("DEFAULT_DISPATCHER_USERNAME", "dispatcher1"),
            "password": _env("DEFAULT_DISPATCHER_PASSWORD", "Dispatcher@12345"),
            "template_key": "dispatcher",
            "role_name": "default-dispatcher-role",
        },
        {
            "role_key": "inspector",
            "username": _env("DEFAULT_INSPECTOR_USERNAME", "inspector1"),
            "password": _env("DEFAULT_INSPECTOR_PASSWORD", "Inspector@12345"),
            "template_key": "inspector",
            "role_name": "default-inspector-role",
        },
        {
            "role_key": "incident_operator",
            "username": _env("DEFAULT_INCIDENT_USERNAME", "incident1"),
            "password": _env("DEFAULT_INCIDENT_PASSWORD", "Incident@12345"),
            "template_key": "incident_operator",
            "role_name": "default-incident-role",
        },
        {
            "role_key": "auditor",
            "username": _env("DEFAULT_AUDITOR_USERNAME", "auditor1"),
            "password": _env("DEFAULT_AUDITOR_PASSWORD", "Auditor@12345"),
            "template_key": "auditor",
            "role_name": "default-auditor-role",
        },
    ]

    output_file = Path(_env("DEFAULT_ACCOUNTS_OUTPUT", "logs/default_accounts.json"))
    timeout = httpx.Timeout(20.0)
    async with httpx.AsyncClient(base_url=base_url, timeout=timeout) as client:
        await _wait_ok(client, "/healthz")
        await _wait_ok(client, "/readyz")

        tenant_id, real_tenant_name = await _create_tenant(client, tenant_name)

        bootstrap_resp = await client.post(
            "/api/identity/bootstrap-admin",
            json={"tenant_id": tenant_id, "username": admin_username, "password": admin_password},
        )
        _assert_status(bootstrap_resp, 201)

        login_resp = await client.post(
            "/api/identity/dev-login",
            json={"tenant_id": tenant_id, "username": admin_username, "password": admin_password},
        )
        _assert_status(login_resp, 200)
        admin_token = login_resp.json()["access_token"]
        headers = _auth_headers(admin_token)

        created_accounts: list[dict[str, str]] = [
            {"role": "admin", "username": admin_username, "password": admin_password}
        ]

        for item in role_accounts:
            user_resp = await client.post(
                "/api/identity/users",
                json={"username": item["username"], "password": item["password"], "is_active": True},
                headers=headers,
            )
            _assert_status(user_resp, 201)
            user_id = user_resp.json()["id"]

            role_resp = await client.post(
                "/api/identity/roles:from-template",
                json={"template_key": item["template_key"], "name": item["role_name"]},
                headers=headers,
            )
            _assert_status(role_resp, 201)
            role_id = role_resp.json()["id"]

            bind_resp = await client.post(
                f"/api/identity/users/{user_id}/roles/{role_id}",
                headers=headers,
            )
            _assert_status(bind_resp, 204)

            created_accounts.append(
                {
                    "role": item["role_key"],
                    "username": item["username"],
                    "password": item["password"],
                }
            )

    result = {
        "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "base_url": base_url,
        "ui_login_url": f"{base_url}/ui/login",
        "tenant": {"id": tenant_id, "name": real_tenant_name},
        "accounts": created_accounts,
        "note": "For local/demo use only. Change all default passwords before non-dev usage.",
    }

    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print("bootstrap_default_accounts: ok")
    print(f"credentials_file: {output_file.as_posix()}")
    print(json.dumps(result, ensure_ascii=False, indent=2))


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
