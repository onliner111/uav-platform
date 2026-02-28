from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime, timedelta

import httpx
from demo_common import assert_status, auth_headers, bootstrap_admin, wait_ok


async def _run() -> None:
    base_url = os.getenv("APP_BASE_URL", "http://app:8000").rstrip("/")
    timeout = httpx.Timeout(20.0)
    async with httpx.AsyncClient(base_url=base_url, timeout=timeout) as client:
        await wait_ok(client, "/healthz")
        await wait_ok(client, "/readyz")

        tenant_id, token = await bootstrap_admin(client, "phase25")
        now = datetime.now(UTC)

        shift_resp = await client.post(
            "/api/alert/oncall/shifts",
            json={
                "shift_name": "phase25-shift",
                "target": "phase25-oncall",
                "starts_at": (now - timedelta(hours=1)).isoformat(),
                "ends_at": (now + timedelta(hours=2)).isoformat(),
                "timezone": "UTC",
                "is_active": True,
                "detail": {"source": "phase25-demo"},
            },
            headers=auth_headers(token),
        )
        assert_status(shift_resp, 201)

        ingest_resp = await client.post(
            "/api/observability/signals:ingest",
            json={
                "items": [
                    {
                        "signal_type": "METRIC",
                        "level": "INFO",
                        "service_name": "dispatch-core",
                        "signal_name": "request",
                        "status_code": 200,
                        "duration_ms": 100,
                        "numeric_value": 1.0,
                        "unit": "count",
                        "occurred_at": now.isoformat(),
                    },
                    {
                        "signal_type": "METRIC",
                        "level": "ERROR",
                        "service_name": "dispatch-core",
                        "signal_name": "request",
                        "status_code": 500,
                        "duration_ms": 820,
                        "numeric_value": 1.0,
                        "unit": "count",
                        "occurred_at": now.isoformat(),
                    },
                ]
            },
            headers=auth_headers(token),
        )
        assert_status(ingest_resp, 201)

        policy_resp = await client.post(
            "/api/observability/slo/policies",
            json={
                "policy_key": "dispatch-availability",
                "service_name": "dispatch-core",
                "signal_name": "request",
                "target_ratio": 0.95,
                "window_minutes": 60,
                "minimum_samples": 1,
                "alert_severity": "P2",
            },
            headers=auth_headers(token),
        )
        assert_status(policy_resp, 201)

        eval_resp = await client.post(
            "/api/observability/slo:evaluate",
            json={"dry_run": False},
            headers=auth_headers(token),
        )
        assert_status(eval_resp, 200)
        if eval_resp.json()["alerts_created"] < 1:
            raise RuntimeError("phase25 demo expected at least one SLO alert")

        alerts_resp = await client.get("/api/observability/alerts?source=SLO", headers=auth_headers(token))
        assert_status(alerts_resp, 200)
        alerts = alerts_resp.json()
        if not alerts or alerts[0].get("target") != "phase25-oncall":
            raise RuntimeError("phase25 demo expected SLO alert routed to oncall target")

        backup_resp = await client.post(
            "/api/observability/backups:runs",
            json={"run_type": "FULL", "is_drill": True},
            headers=auth_headers(token),
        )
        assert_status(backup_resp, 201)
        backup_id = backup_resp.json()["id"]

        restore_resp = await client.post(
            f"/api/observability/backups/runs/{backup_id}:restore-drill",
            json={"objective_rto_seconds": 300, "simulated_restore_seconds": 180},
            headers=auth_headers(token),
        )
        assert_status(restore_resp, 201)
        if restore_resp.json()["status"] != "PASSED":
            raise RuntimeError("phase25 demo expected restore drill status PASSED")

        inspect_resp = await client.post(
            "/api/observability/security-inspections:runs",
            json={"baseline_version": "phase25-v1"},
            headers=auth_headers(token),
        )
        assert_status(inspect_resp, 201)
        if inspect_resp.json()["total_checks"] < 1:
            raise RuntimeError("phase25 demo expected non-empty security inspection checks")

        policy_upsert = await client.put(
            "/api/observability/capacity/policies/cpu.utilization",
            json={
                "target_utilization_pct": 75,
                "scale_out_threshold_pct": 85,
                "scale_in_threshold_pct": 50,
                "min_replicas": 1,
                "max_replicas": 5,
                "current_replicas": 2,
                "is_active": True,
            },
            headers=auth_headers(token),
        )
        assert_status(policy_upsert, 200)

        cpu_ingest = await client.post(
            "/api/observability/signals:ingest",
            json={
                "items": [
                    {
                        "signal_type": "METRIC",
                        "level": "INFO",
                        "service_name": "platform-runtime",
                        "signal_name": "cpu.utilization",
                        "numeric_value": 91.0,
                        "unit": "percent",
                        "occurred_at": now.isoformat(),
                    },
                    {
                        "signal_type": "METRIC",
                        "level": "INFO",
                        "service_name": "platform-runtime",
                        "signal_name": "cpu.utilization",
                        "numeric_value": 90.0,
                        "unit": "percent",
                        "occurred_at": now.isoformat(),
                    },
                ]
            },
            headers=auth_headers(token),
        )
        assert_status(cpu_ingest, 201)

        forecast_resp = await client.post(
            "/api/observability/capacity:forecast",
            json={"meter_key": "cpu.utilization", "window_minutes": 60, "sample_minutes": 180},
            headers=auth_headers(token),
        )
        assert_status(forecast_resp, 201)
        forecast = forecast_resp.json()
        if forecast["decision"] != "SCALE_OUT":
            raise RuntimeError("phase25 demo expected capacity decision SCALE_OUT")

    print("demo_phase25_observability_reliability: ok")


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
