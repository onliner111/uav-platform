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

        _tenant_id, token = await bootstrap_admin(client, "phase31")

        now = datetime.now(UTC)
        shift_resp = await client.post(
            "/api/alert/oncall/shifts",
            json={
                "shift_name": "phase31-watch",
                "target": "oncall-phase31",
                "starts_at": (now - timedelta(hours=1)).isoformat(),
                "ends_at": (now + timedelta(hours=2)).isoformat(),
                "timezone": "UTC",
                "is_active": True,
                "detail": {"source": "phase31-demo"},
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
                        "service_name": "mission-dispatch",
                        "signal_name": "request",
                        "status_code": 200,
                        "duration_ms": 120,
                        "numeric_value": 1.0,
                        "unit": "count",
                        "occurred_at": now.isoformat(),
                    },
                    {
                        "signal_type": "METRIC",
                        "level": "ERROR",
                        "service_name": "mission-dispatch",
                        "signal_name": "request",
                        "status_code": 500,
                        "duration_ms": 920,
                        "numeric_value": 1.0,
                        "unit": "count",
                        "occurred_at": now.isoformat(),
                    },
                    {
                        "signal_type": "TRACE",
                        "level": "INFO",
                        "service_name": "mission-dispatch",
                        "signal_name": "request",
                        "trace_id": "phase31-trace-001",
                        "span_id": "phase31-span-001",
                        "duration_ms": 260,
                        "occurred_at": now.isoformat(),
                    },
                ]
            },
            headers=auth_headers(token),
        )
        assert_status(ingest_resp, 201)
        if ingest_resp.json()["accepted_count"] != 3:
            raise RuntimeError("phase31 demo expected 3 accepted observability signals")

        policy_resp = await client.post(
            "/api/observability/slo/policies",
            json={
                "policy_key": "phase31-dispatch-availability",
                "service_name": "mission-dispatch",
                "signal_name": "request",
                "target_ratio": 0.95,
                "window_minutes": 60,
                "minimum_samples": 1,
                "alert_severity": "P2",
                "detail": {"source": "phase31-demo"},
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
        eval_payload = eval_resp.json()
        if eval_payload["evaluated_count"] < 1:
            raise RuntimeError("phase31 demo expected at least one evaluated SLO policy")

        alerts_resp = await client.get(
            "/api/observability/alerts?source=SLO",
            headers=auth_headers(token),
        )
        assert_status(alerts_resp, 200)
        if not alerts_resp.json():
            raise RuntimeError("phase31 demo expected generated observability alerts")

        backup_resp = await client.post(
            "/api/observability/backups:runs",
            json={"run_type": "FULL", "is_drill": True, "detail": {"source": "phase31-demo"}},
            headers=auth_headers(token),
        )
        assert_status(backup_resp, 201)
        backup_id = backup_resp.json()["id"]

        restore_resp = await client.post(
            f"/api/observability/backups/runs/{backup_id}:restore-drill",
            json={
                "objective_rto_seconds": 300,
                "simulated_restore_seconds": 180,
                "detail": {"source": "phase31-demo"},
            },
            headers=auth_headers(token),
        )
        assert_status(restore_resp, 201)
        if restore_resp.json()["status"] != "PASSED":
            raise RuntimeError("phase31 demo expected restore drill to pass")

        inspection_resp = await client.post(
            "/api/observability/security-inspections:runs",
            json={"baseline_version": "phase31-v1", "detail": {"source": "phase31-demo"}},
            headers=auth_headers(token),
        )
        assert_status(inspection_resp, 201)
        if inspection_resp.json()["total_checks"] < 1:
            raise RuntimeError("phase31 demo expected security inspection checks")

        capacity_policy_resp = await client.put(
            "/api/observability/capacity/policies/cpu.utilization",
            json={
                "target_utilization_pct": 75,
                "scale_out_threshold_pct": 85,
                "scale_in_threshold_pct": 50,
                "min_replicas": 1,
                "max_replicas": 5,
                "current_replicas": 2,
                "is_active": True,
                "detail": {"source": "phase31-demo"},
            },
            headers=auth_headers(token),
        )
        assert_status(capacity_policy_resp, 200)

        cpu_metrics_resp = await client.post(
            "/api/observability/signals:ingest",
            json={
                "items": [
                    {
                        "signal_type": "METRIC",
                        "level": "INFO",
                        "service_name": "platform-runtime",
                        "signal_name": "cpu.utilization",
                        "numeric_value": 92.0,
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
        assert_status(cpu_metrics_resp, 201)

        forecast_resp = await client.post(
            "/api/observability/capacity:forecast",
            json={"meter_key": "cpu.utilization", "window_minutes": 60, "sample_minutes": 180},
            headers=auth_headers(token),
        )
        assert_status(forecast_resp, 201)
        if forecast_resp.json()["decision"] != "SCALE_OUT":
            raise RuntimeError("phase31 demo expected a scale-out recommendation")

        ui_checks = [
            ("/ui/observability", "Observability + SLO Command"),
            ("/ui/observability", "Oncall Replay + Alert Linkage"),
            ("/ui/reliability", "Reliability Runbook Operations"),
            ("/ui/reliability", "Capacity Forecast Board"),
        ]
        for path, expected_text in ui_checks:
            response = await client.get(f"{path}?token={token}")
            assert_status(response, 200)
            if expected_text not in response.text:
                raise RuntimeError(f"phase31 demo expected '{expected_text}' in {path}")

    print("demo_phase31_observability_reliability_ops_console: ok")


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
