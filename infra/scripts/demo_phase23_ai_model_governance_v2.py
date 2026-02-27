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

        _tenant_id, token = await bootstrap_admin(client, "phase23")

        model_resp = await client.post(
            "/api/ai/models",
            json={
                "model_key": "builtin:uav-assistant-lite",
                "provider": "builtin",
                "display_name": "uav-assistant-lite",
                "description": "phase23 demo model",
            },
            headers=auth_headers(token),
        )
        assert_status(model_resp, 201)
        model_id = model_resp.json()["id"]

        stable_resp = await client.post(
            f"/api/ai/models/{model_id}/versions",
            json={
                "version": "phase23.demo.v1",
                "status": "STABLE",
                "threshold_defaults": {"confidence_min": 0.8},
            },
            headers=auth_headers(token),
        )
        assert_status(stable_resp, 201)
        stable_id = stable_resp.json()["id"]

        canary_resp = await client.post(
            f"/api/ai/models/{model_id}/versions",
            json={
                "version": "phase23.demo.v2",
                "status": "CANARY",
                "threshold_defaults": {"confidence_min": 0.7},
            },
            headers=auth_headers(token),
        )
        assert_status(canary_resp, 201)
        canary_id = canary_resp.json()["id"]

        policy_resp = await client.put(
            f"/api/ai/models/{model_id}/rollout-policy",
            json={
                "default_version_id": stable_id,
                "traffic_allocation": [
                    {"version_id": stable_id, "weight": 80},
                    {"version_id": canary_id, "weight": 20},
                ],
                "threshold_overrides": {"confidence_min": 0.75},
                "is_active": True,
            },
            headers=auth_headers(token),
        )
        assert_status(policy_resp, 200)

        job_resp = await client.post(
            "/api/ai/jobs",
            json={
                "job_type": "SUMMARY",
                "trigger_mode": "NEAR_REALTIME",
                "model_version_id": stable_id,
            },
            headers=auth_headers(token),
        )
        assert_status(job_resp, 201)
        job_id = job_resp.json()["id"]

        forced_run_resp = await client.post(
            f"/api/ai/jobs/{job_id}/runs",
            json={
                "force_model_version_id": canary_id,
                "force_threshold_config": {"confidence_min": 0.72},
                "context": {"case": "phase23-demo-force"},
            },
            headers=auth_headers(token),
        )
        assert_status(forced_run_resp, 201)
        if forced_run_resp.json()["metrics"]["selection_source"] != "MANUAL_FORCE":
            raise RuntimeError("expected manual force selection source")

        tick_first = await client.post(
            "/api/ai/jobs:schedule-tick",
            json={"window_key": "phase23-demo-window", "job_ids": [job_id], "max_jobs": 10},
            headers=auth_headers(token),
        )
        assert_status(tick_first, 200)
        if tick_first.json()["triggered_jobs"] != 1:
            raise RuntimeError(f"expected triggered_jobs=1, got {tick_first.json()}")

        tick_second = await client.post(
            "/api/ai/jobs:schedule-tick",
            json={"window_key": "phase23-demo-window", "job_ids": [job_id], "max_jobs": 10},
            headers=auth_headers(token),
        )
        assert_status(tick_second, 200)
        if tick_second.json()["triggered_jobs"] != 0:
            raise RuntimeError(f"expected idempotent second tick, got {tick_second.json()}")

        recompute_resp = await client.post(
            "/api/ai/evaluations:recompute",
            json={"job_id": job_id},
            headers=auth_headers(token),
        )
        assert_status(recompute_resp, 200)
        if len(recompute_resp.json()) < 1:
            raise RuntimeError("expected at least one evaluation summary")

        compare_resp = await client.get(
            f"/api/ai/evaluations/compare?left_version_id={stable_id}&right_version_id={canary_id}&job_id={job_id}",
            headers=auth_headers(token),
        )
        assert_status(compare_resp, 200)

        rollback_resp = await client.post(
            f"/api/ai/models/{model_id}/rollout-policy:rollback",
            json={"target_version_id": stable_id, "reason": "phase23 demo rollback"},
            headers=auth_headers(token),
        )
        assert_status(rollback_resp, 200)
        if rollback_resp.json()["traffic_allocation"] != [{"version_id": stable_id, "weight": 100}]:
            raise RuntimeError(f"unexpected rollback policy payload: {rollback_resp.json()}")

    print("demo_phase23_ai_model_governance_v2: ok")


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
