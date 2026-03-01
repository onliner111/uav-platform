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

        _tenant_id, token = await bootstrap_admin(client, "phase29")
        template_id = await create_template(client, token, name="phase29-template")
        task_id = await create_inspection_task(client, token, template_id, name="phase29-task")

        raw_resp = await client.post(
            "/api/outcomes/raw",
            json={
                "task_id": task_id,
                "data_type": "IMAGE",
                "source_uri": "s3://phase29-bucket/raw/demo-image.jpg",
                "checksum": "phase29-checksum",
                "meta": {"source": "phase29-demo"},
            },
            headers=auth_headers(token),
        )
        assert_status(raw_resp, 201)
        raw_id = raw_resp.json()["id"]

        raw_transition_resp = await client.patch(
            f"/api/outcomes/raw/{raw_id}/storage",
            json={"access_tier": "COLD", "storage_region": "cn-hb-1"},
            headers=auth_headers(token),
        )
        assert_status(raw_transition_resp, 200)
        if raw_transition_resp.json()["access_tier"] != "COLD":
            raise RuntimeError("phase29 demo expected raw data access tier transitioned to COLD")

        raw_list_resp = await client.get(
            f"/api/outcomes/raw?task_id={task_id}&data_type=IMAGE",
            headers=auth_headers(token),
        )
        assert_status(raw_list_resp, 200)
        raw_rows = raw_list_resp.json()
        if not any(item["id"] == raw_id for item in raw_rows):
            raise RuntimeError("phase29 demo expected created raw record in filtered list")

        outcome_resp = await client.post(
            "/api/outcomes/records",
            json={
                "task_id": task_id,
                "source_type": "MANUAL",
                "source_id": "phase29-manual-source",
                "outcome_type": "DEFECT",
                "status": "NEW",
                "point_lat": 30.59,
                "point_lon": 114.30,
                "confidence": 0.91,
                "payload": {"title": "phase29 outcome"},
            },
            headers=auth_headers(token),
        )
        assert_status(outcome_resp, 201)
        outcome_id = outcome_resp.json()["id"]

        outcome_status_resp = await client.patch(
            f"/api/outcomes/records/{outcome_id}/status",
            json={"status": "VERIFIED", "note": "phase29 verified"},
            headers=auth_headers(token),
        )
        assert_status(outcome_status_resp, 200)
        if outcome_status_resp.json()["status"] != "VERIFIED":
            raise RuntimeError("phase29 demo expected outcome status VERIFIED")

        outcome_versions_resp = await client.get(
            f"/api/outcomes/records/{outcome_id}/versions",
            headers=auth_headers(token),
        )
        assert_status(outcome_versions_resp, 200)
        if len(outcome_versions_resp.json()) < 2:
            raise RuntimeError("phase29 demo expected outcome version chain after status update")

        report_template_resp = await client.post(
            "/api/reporting/outcome-report-templates",
            json={
                "name": "phase29-template",
                "format_default": "PDF",
                "title_template": "Phase29 Outcome Report",
                "body_template": "task={{ task_id }}",
                "is_active": True,
            },
            headers=auth_headers(token),
        )
        assert_status(report_template_resp, 201)
        report_template_id = report_template_resp.json()["id"]

        export_resp = await client.post(
            "/api/reporting/outcome-report-exports",
            json={
                "template_id": report_template_id,
                "report_format": "PDF",
                "task_id": task_id,
                "topic": "phase29",
            },
            headers=auth_headers(token),
        )
        assert_status(export_resp, 201)
        export_id = export_resp.json()["id"]

        export_list_resp = await client.get(
            "/api/reporting/outcome-report-exports?limit=10",
            headers=auth_headers(token),
        )
        assert_status(export_list_resp, 200)
        if not any(item["id"] == export_id for item in export_list_resp.json()):
            raise RuntimeError("phase29 demo expected created report export in list API")

        export_detail_resp = await client.get(
            f"/api/reporting/outcome-report-exports/{export_id}",
            headers=auth_headers(token),
        )
        assert_status(export_detail_resp, 200)
        if export_detail_resp.json()["status"] != "SUCCEEDED":
            raise RuntimeError("phase29 demo expected report export succeeded")

        retention_resp = await client.post(
            "/api/reporting/outcome-report-exports:retention",
            json={"retention_days": 30, "dry_run": True},
            headers=auth_headers(token),
        )
        assert_status(retention_resp, 200)
        if "scanned_count" not in retention_resp.json():
            raise RuntimeError("phase29 demo expected retention run summary")

        model_resp = await client.post(
            "/api/ai/models",
            json={
                "model_key": "phase29-risk-model",
                "provider": "builtin",
                "display_name": "Phase29 Risk Model",
                "description": "phase29 demo model",
                "is_active": True,
            },
            headers=auth_headers(token),
        )
        assert_status(model_resp, 201)
        model_id = model_resp.json()["id"]

        version_v1_resp = await client.post(
            f"/api/ai/models/{model_id}/versions",
            json={
                "version": "v1",
                "status": "DRAFT",
                "threshold_defaults": {"risk_threshold": 0.75},
                "detail": {"phase": 29},
            },
            headers=auth_headers(token),
        )
        assert_status(version_v1_resp, 201)
        version_v1_id = version_v1_resp.json()["id"]

        version_v2_resp = await client.post(
            f"/api/ai/models/{model_id}/versions",
            json={
                "version": "v2",
                "status": "CANARY",
                "threshold_defaults": {"risk_threshold": 0.82},
                "detail": {"phase": 29},
            },
            headers=auth_headers(token),
        )
        assert_status(version_v2_resp, 201)
        version_v2_id = version_v2_resp.json()["id"]

        promote_resp = await client.post(
            f"/api/ai/models/{model_id}/versions/{version_v1_id}:promote",
            json={"target_status": "STABLE", "note": "phase29 stable"},
            headers=auth_headers(token),
        )
        assert_status(promote_resp, 200)
        if promote_resp.json()["status"] != "STABLE":
            raise RuntimeError("phase29 demo expected model version promoted to STABLE")

        rollout_upsert_resp = await client.put(
            f"/api/ai/models/{model_id}/rollout-policy",
            json={
                "default_version_id": version_v1_id,
                "traffic_allocation": [
                    {"version_id": version_v1_id, "weight": 80},
                    {"version_id": version_v2_id, "weight": 20},
                ],
                "threshold_overrides": {"risk_threshold": 0.79},
                "detail": {"mode": "canary"},
                "is_active": True,
            },
            headers=auth_headers(token),
        )
        assert_status(rollout_upsert_resp, 200)
        if len(rollout_upsert_resp.json().get("traffic_allocation", [])) != 2:
            raise RuntimeError("phase29 demo expected two rollout traffic entries")

        rollout_get_resp = await client.get(
            f"/api/ai/models/{model_id}/rollout-policy",
            headers=auth_headers(token),
        )
        assert_status(rollout_get_resp, 200)
        if rollout_get_resp.json()["default_version_id"] != version_v1_id:
            raise RuntimeError("phase29 demo expected rollout default version equals promoted stable version")

        job_resp = await client.post(
            "/api/ai/jobs",
            json={
                "task_id": task_id,
                "topic": "defect",
                "job_type": "SUMMARY",
                "trigger_mode": "MANUAL",
                "model_version_id": version_v1_id,
                "threshold_config": {"risk_threshold": 0.77},
                "input_config": {"scope": "phase29"},
            },
            headers=auth_headers(token),
        )
        assert_status(job_resp, 201)
        job_id = job_resp.json()["id"]

        bind_job_resp = await client.post(
            f"/api/ai/jobs/{job_id}:bind-model-version",
            json={"model_version_id": version_v1_id},
            headers=auth_headers(token),
        )
        assert_status(bind_job_resp, 200)

        run_v1_resp = await client.post(
            f"/api/ai/jobs/{job_id}/runs",
            json={"force_fail": False, "context": {"source": "phase29"}},
            headers=auth_headers(token),
        )
        assert_status(run_v1_resp, 201)
        if run_v1_resp.json()["status"] != "SUCCEEDED":
            raise RuntimeError("phase29 demo expected ai run succeeded")

        run_v2_resp = await client.post(
            f"/api/ai/jobs/{job_id}/runs",
            json={"force_fail": False, "force_model_version_id": version_v2_id, "context": {"source": "phase29-v2"}},
            headers=auth_headers(token),
        )
        assert_status(run_v2_resp, 201)
        if run_v2_resp.json()["status"] != "SUCCEEDED":
            raise RuntimeError("phase29 demo expected ai forced-version run succeeded")

        failed_run_resp = await client.post(
            f"/api/ai/jobs/{job_id}/runs",
            json={"force_fail": True, "context": {"source": "phase29-fail"}},
            headers=auth_headers(token),
        )
        assert_status(failed_run_resp, 201)
        failed_run_id = failed_run_resp.json()["id"]
        if failed_run_resp.json()["status"] != "FAILED":
            raise RuntimeError("phase29 demo expected forced failed run")

        retry_resp = await client.post(
            f"/api/ai/runs/{failed_run_id}/retry",
            json={"force_fail": False, "context": {"source": "phase29-retry"}},
            headers=auth_headers(token),
        )
        assert_status(retry_resp, 200)
        if retry_resp.json()["status"] != "SUCCEEDED":
            raise RuntimeError("phase29 demo expected retry run succeeded")

        runs_resp = await client.get(f"/api/ai/jobs/{job_id}/runs", headers=auth_headers(token))
        assert_status(runs_resp, 200)
        if len(runs_resp.json()) < 4:
            raise RuntimeError("phase29 demo expected multiple ai runs for governance checks")

        outputs_resp = await client.get(
            f"/api/ai/outputs?job_id={job_id}&review_status=PENDING_REVIEW",
            headers=auth_headers(token),
        )
        assert_status(outputs_resp, 200)
        outputs = outputs_resp.json()
        if not outputs:
            raise RuntimeError("phase29 demo expected pending review ai outputs")
        output_id = outputs[0]["id"]

        review_bundle_resp = await client.get(
            f"/api/ai/outputs/{output_id}/review",
            headers=auth_headers(token),
        )
        assert_status(review_bundle_resp, 200)
        if review_bundle_resp.json()["output"]["id"] != output_id:
            raise RuntimeError("phase29 demo expected review bundle output id matched")

        review_action_resp = await client.post(
            f"/api/ai/outputs/{output_id}/review",
            json={"action_type": "APPROVE", "note": "phase29 approve"},
            headers=auth_headers(token),
        )
        assert_status(review_action_resp, 200)

        recompute_resp = await client.post(
            "/api/ai/evaluations:recompute",
            json={"model_id": model_id},
            headers=auth_headers(token),
        )
        assert_status(recompute_resp, 200)
        if not recompute_resp.json():
            raise RuntimeError("phase29 demo expected recompute evaluations not empty")

        compare_resp = await client.get(
            f"/api/ai/evaluations/compare?left_version_id={version_v1_id}&right_version_id={version_v2_id}&job_id={job_id}",
            headers=auth_headers(token),
        )
        assert_status(compare_resp, 200)
        compare_payload = compare_resp.json()
        if compare_payload["left"]["model_version_id"] != version_v1_id:
            raise RuntimeError("phase29 demo expected compare payload left version id matched")

        rollback_resp = await client.post(
            f"/api/ai/models/{model_id}/rollout-policy:rollback",
            json={"target_version_id": version_v1_id, "reason": "phase29 rollback check"},
            headers=auth_headers(token),
        )
        assert_status(rollback_resp, 200)
        if rollback_resp.json()["default_version_id"] != version_v1_id:
            raise RuntimeError("phase29 demo expected rollback default version set to target")

        ui_checks = [
            ("/ui/reports", "Data Outcomes Workbench"),
            ("/ui/reports", "Reporting Center"),
            ("/ui/ai-governance", "Model Catalog + Version Governance"),
            ("/ui/ai-governance", "Output Review + Evidence Chain"),
        ]
        for path, expected_text in ui_checks:
            response = await client.get(f"{path}?token={token}")
            assert_status(response, 200)
            if expected_text not in response.text:
                raise RuntimeError(f"phase29 demo expected '{expected_text}' in {path}")

    print("demo_phase29_data_ai_governance_ui: ok")


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
