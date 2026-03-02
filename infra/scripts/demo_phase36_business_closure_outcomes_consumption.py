from __future__ import annotations

import asyncio
import os

import httpx
from demo_common import assert_status, bootstrap_admin, wait_ok


async def _run() -> None:
    base_url = os.getenv("APP_BASE_URL", "http://app:8000").rstrip("/")
    timeout = httpx.Timeout(20.0)
    async with httpx.AsyncClient(base_url=base_url, timeout=timeout) as client:
        await wait_ok(client, "/healthz")
        await wait_ok(client, "/readyz")

        _tenant_id, token = await bootstrap_admin(client, "phase36")
        headers = {"Authorization": f"Bearer {token}"}

        create_outcome_resp = await client.post(
            "/api/outcomes/records",
            json={
                "source_type": "MANUAL",
                "source_id": "phase36-manual-source",
                "outcome_type": "DEFECT",
                "payload": {"note": "phase36 business closure case"},
            },
            headers=headers,
        )
        assert_status(create_outcome_resp, 201)
        outcome_id = create_outcome_resp.json()["id"]

        verify_outcome_resp = await client.patch(
            f"/api/outcomes/records/{outcome_id}/status",
            json={"status": "VERIFIED", "note": "phase36 verified"},
            headers=headers,
        )
        assert_status(verify_outcome_resp, 200)

        create_template_resp = await client.post(
            "/api/reporting/outcome-report-templates",
            json={
                "name": "phase36-template",
                "format_default": "PDF",
                "title_template": "phase36 report count={count}",
                "body_template": "topic={topic}",
                "is_active": True,
            },
            headers=headers,
        )
        assert_status(create_template_resp, 201)
        template_id = create_template_resp.json()["id"]

        create_export_resp = await client.post(
            "/api/reporting/outcome-report-exports",
            json={"template_id": template_id, "topic": "phase36"},
            headers=headers,
        )
        assert_status(create_export_resp, 201)

        reports_page = await client.get(f"/ui/reports?token={token}")
        assert_status(reports_page, 200)
        for marker in (
            "问题闭环看板",
            "成果审核与复核工作台",
            "典型案例与专题视图",
            "领导汇报与专题分析",
            "生成汇报材料",
        ):
            if marker not in reports_page.text:
                raise RuntimeError(f"phase36 reports page missing marker: {marker}")

    print("demo_phase36_business_closure_outcomes_consumption: ok")


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
