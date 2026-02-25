from __future__ import annotations

import asyncio
import os

import httpx
from demo_common import (
    assert_status,
    auth_headers,
    bootstrap_admin,
    create_inspection_task,
    create_template,
    wait_ok,
)


async def _run() -> None:
    base_url = os.getenv("APP_BASE_URL", "http://app:8000").rstrip("/")
    timeout = httpx.Timeout(20.0)
    async with httpx.AsyncClient(base_url=base_url, timeout=timeout) as client:
        await wait_ok(client, "/healthz")
        await wait_ok(client, "/readyz")

        _tenant_id, token = await bootstrap_admin(client, "phase14")

        template_id = await create_template(client, token, "phase14-template")
        task_id = await create_inspection_task(client, token, template_id, name="phase14-task")

        observation_resp = await client.post(
            f"/api/inspection/tasks/{task_id}/observations",
            json={
                "position_lat": 30.5801,
                "position_lon": 114.3001,
                "alt_m": 44.0,
                "item_code": "PH14-OBS",
                "severity": 2,
                "note": "phase14 observation",
                "confidence": 0.89,
            },
            headers=auth_headers(token),
        )
        assert_status(observation_resp, 201)

        alert_ingest = await client.post(
            "/api/telemetry/ingest",
            json={
                "tenant_id": "spoofed",
                "drone_id": "phase14-drone",
                "position": {"lat": 30.12, "lon": 114.45, "alt_m": 120.0},
                "battery": {"percent": 11.0},
                "link": {"latency_ms": 100},
                "mode": "AUTO",
                "health": {"low_battery": True},
            },
            headers=auth_headers(token),
        )
        assert_status(alert_ingest, 200)

        create_job_resp = await client.post(
            "/api/ai/jobs",
            json={
                "task_id": task_id,
                "topic": "battery",
                "job_type": "SUMMARY",
                "trigger_mode": "MANUAL",
                "model_version": "phase14.demo.v1",
            },
            headers=auth_headers(token),
        )
        assert_status(create_job_resp, 201)
        job_id = create_job_resp.json()["id"]

        run_resp = await client.post(
            f"/api/ai/jobs/{job_id}/runs",
            json={"force_fail": False, "context": {"source": "phase14-demo"}},
            headers=auth_headers(token),
        )
        assert_status(run_resp, 201)
        if run_resp.json()["status"] != "SUCCEEDED":
            raise RuntimeError(f"expected run succeeded, got {run_resp.json()}")

        outputs_resp = await client.get(f"/api/ai/outputs?job_id={job_id}", headers=auth_headers(token))
        assert_status(outputs_resp, 200)
        outputs = outputs_resp.json()
        if not outputs:
            raise RuntimeError("expected ai output")
        output = outputs[0]
        if output["control_allowed"]:
            raise RuntimeError("ai output must never have flight control permission")
        output_id = output["id"]

        review_view_resp = await client.get(
            f"/api/ai/outputs/{output_id}/review",
            headers=auth_headers(token),
        )
        assert_status(review_view_resp, 200)
        evidence_types = {item["evidence_type"] for item in review_view_resp.json().get("evidences", [])}
        required_evidence = {"MODEL_CONFIG", "INPUT_SNAPSHOT", "OUTPUT_SNAPSHOT", "TRACE"}
        if not required_evidence.issubset(evidence_types):
            raise RuntimeError(f"incomplete evidence chain: {evidence_types}")

        override_resp = await client.post(
            f"/api/ai/outputs/{output_id}/review",
            json={
                "action_type": "OVERRIDE",
                "note": "manual override in demo",
                "override_payload": {
                    "summary": "manual summary for phase14 demo",
                    "suggestion": "manual suggestion for phase14 demo",
                },
            },
            headers=auth_headers(token),
        )
        assert_status(override_resp, 200)

        run_failed_resp = await client.post(
            f"/api/ai/jobs/{job_id}/runs",
            json={"force_fail": True, "context": {"source": "phase14-demo-retry"}},
            headers=auth_headers(token),
        )
        assert_status(run_failed_resp, 201)
        if run_failed_resp.json()["status"] != "FAILED":
            raise RuntimeError("expected forced failed run")
        failed_run_id = run_failed_resp.json()["id"]

        retry_resp = await client.post(
            f"/api/ai/runs/{failed_run_id}/retry",
            json={"force_fail": False, "context": {"source": "phase14-demo-retry-ok"}},
            headers=auth_headers(token),
        )
        assert_status(retry_resp, 200)
        if retry_resp.json()["status"] != "SUCCEEDED":
            raise RuntimeError(f"expected retry succeeded, got {retry_resp.json()}")

    print("demo_phase14_ai_evidence: ok")


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
