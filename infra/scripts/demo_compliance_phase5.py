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

        _tenant_id, token = await bootstrap_admin(client, "phase5")

        create_resp = await client.post(
            "/api/approvals",
            json={"entity_type": "inspection_task", "entity_id": "task-demo", "status": "APPROVED"},
            headers=auth_headers(token),
        )
        assert_status(create_resp, 200)
        approval_id = create_resp.json()["id"]

        list_resp = await client.get("/api/approvals", headers=auth_headers(token))
        assert_status(list_resp, 200)
        ids = {item["id"] for item in list_resp.json()}
        if approval_id not in ids:
            raise RuntimeError("approval record not listed")

        export_resp = await client.get("/api/approvals/audit-export", headers=auth_headers(token))
        assert_status(export_resp, 200)
        file_path = export_resp.json().get("file_path")
        if not file_path:
            raise RuntimeError("audit export did not return file_path")

    print("demo_compliance_phase5: ok")


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
