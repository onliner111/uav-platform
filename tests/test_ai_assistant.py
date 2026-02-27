from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlmodel import SQLModel, create_engine

from app import main as app_main
from app.infra import audit, db, events


@pytest.fixture()
def ai_client(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Generator[TestClient, None, None]:
    db_path = tmp_path / "ai_test.db"
    test_engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(test_engine, "connect")
    def _enable_foreign_keys(dbapi_connection: object, _connection_record: object) -> None:
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    SQLModel.metadata.create_all(test_engine)
    monkeypatch.setattr(db, "engine", test_engine)
    monkeypatch.setattr(audit, "engine", test_engine)
    monkeypatch.setattr(events, "engine", test_engine)

    client = TestClient(app_main.app)
    yield client
    client.close()
    app_main.app.dependency_overrides.clear()


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_tenant(client: TestClient, name: str) -> str:
    response = client.post("/api/identity/tenants", json={"name": name})
    assert response.status_code == 201
    return response.json()["id"]


def _bootstrap_admin(client: TestClient, tenant_id: str, username: str, password: str) -> None:
    response = client.post(
        "/api/identity/bootstrap-admin",
        json={"tenant_id": tenant_id, "username": username, "password": password},
    )
    assert response.status_code == 201


def _login(client: TestClient, tenant_id: str, username: str, password: str) -> str:
    response = client.post(
        "/api/identity/dev-login",
        json={"tenant_id": tenant_id, "username": username, "password": password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _create_template(client: TestClient, token: str, name: str) -> str:
    response = client.post(
        "/api/inspection/templates",
        json={"name": name, "category": "phase14", "description": "phase14", "is_active": True},
        headers=_auth_header(token),
    )
    assert response.status_code == 201
    return response.json()["id"]


def _create_task(client: TestClient, token: str, template_id: str, name: str) -> str:
    response = client.post(
        "/api/inspection/tasks",
        json={
            "name": name,
            "template_id": template_id,
            "area_geom": "POLYGON((114.30 30.58,114.31 30.58,114.31 30.59,114.30 30.59,114.30 30.58))",
            "priority": 3,
            "status": "SCHEDULED",
        },
        headers=_auth_header(token),
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_ai_evidence_chain_and_human_override(ai_client: TestClient) -> None:
    tenant_id = _create_tenant(ai_client, "phase14-ai-evidence")
    _bootstrap_admin(ai_client, tenant_id, "admin", "admin-pass")
    token = _login(ai_client, tenant_id, "admin", "admin-pass")

    template_id = _create_template(ai_client, token, "phase14-template")
    task_id = _create_task(ai_client, token, template_id, "phase14-task")

    obs_resp = ai_client.post(
        f"/api/inspection/tasks/{task_id}/observations",
        json={
            "position_lat": 30.5801,
            "position_lon": 114.3001,
            "alt_m": 45.0,
            "item_code": "P14-A",
            "severity": 2,
            "note": "phase14 observation",
            "confidence": 0.9,
        },
        headers=_auth_header(token),
    )
    assert obs_resp.status_code == 201

    alert_resp = ai_client.post(
        "/api/telemetry/ingest",
        json={
            "tenant_id": "spoofed",
            "drone_id": "phase14-drone",
            "position": {"lat": 30.12, "lon": 114.45, "alt_m": 120.0},
            "battery": {"percent": 10.0},
            "link": {"latency_ms": 100},
            "mode": "AUTO",
            "health": {"low_battery": True},
        },
        headers=_auth_header(token),
    )
    assert alert_resp.status_code == 200

    job_resp = ai_client.post(
        "/api/ai/jobs",
        json={
            "task_id": task_id,
            "topic": "battery",
            "job_type": "SUMMARY",
            "trigger_mode": "MANUAL",
            "model_version": "phase14.test.v1",
        },
        headers=_auth_header(token),
    )
    assert job_resp.status_code == 201
    job_id = job_resp.json()["id"]

    run_resp = ai_client.post(
        f"/api/ai/jobs/{job_id}/runs",
        json={"force_fail": False, "context": {"source": "unit-test"}},
        headers=_auth_header(token),
    )
    assert run_resp.status_code == 201
    run_id = run_resp.json()["id"]
    assert run_resp.json()["status"] == "SUCCEEDED"

    outputs_resp = ai_client.get(f"/api/ai/outputs?job_id={job_id}", headers=_auth_header(token))
    assert outputs_resp.status_code == 200
    outputs = outputs_resp.json()
    assert len(outputs) == 1
    output_id = outputs[0]["id"]
    assert outputs[0]["run_id"] == run_id
    assert outputs[0]["review_status"] == "PENDING_REVIEW"
    assert outputs[0]["control_allowed"] is False

    review_view_resp = ai_client.get(f"/api/ai/outputs/{output_id}/review", headers=_auth_header(token))
    assert review_view_resp.status_code == 200
    evidence_types = {item["evidence_type"] for item in review_view_resp.json()["evidences"]}
    assert {"MODEL_CONFIG", "INPUT_SNAPSHOT", "OUTPUT_SNAPSHOT", "TRACE"}.issubset(evidence_types)

    override_resp = ai_client.post(
        f"/api/ai/outputs/{output_id}/review",
        json={
            "action_type": "OVERRIDE",
            "note": "human override applied",
            "override_payload": {"summary": "manual summary", "suggestion": "manual suggestion"},
        },
        headers=_auth_header(token),
    )
    assert override_resp.status_code == 200
    assert override_resp.json()["action_type"] == "OVERRIDE"

    output_resp = ai_client.get(f"/api/ai/outputs/{output_id}", headers=_auth_header(token))
    assert output_resp.status_code == 200
    body = output_resp.json()
    assert body["review_status"] == "OVERRIDDEN"
    assert body["summary_text"] == "manual summary"
    assert body["suggestion_text"] == "manual suggestion"
    assert body["reviewed_by"] is not None


def test_ai_retry_and_tenant_boundary(ai_client: TestClient) -> None:
    tenant_a = _create_tenant(ai_client, "phase14-ai-retry-a")
    _bootstrap_admin(ai_client, tenant_a, "admin-a", "admin-pass")
    token_a = _login(ai_client, tenant_a, "admin-a", "admin-pass")

    tenant_b = _create_tenant(ai_client, "phase14-ai-retry-b")
    _bootstrap_admin(ai_client, tenant_b, "admin-b", "admin-pass")
    token_b = _login(ai_client, tenant_b, "admin-b", "admin-pass")

    job_resp = ai_client.post(
        "/api/ai/jobs",
        json={"job_type": "SUGGESTION", "trigger_mode": "MANUAL"},
        headers=_auth_header(token_a),
    )
    assert job_resp.status_code == 201
    job_id = job_resp.json()["id"]

    failed_run_resp = ai_client.post(
        f"/api/ai/jobs/{job_id}/runs",
        json={"force_fail": True, "context": {"case": "retry"}},
        headers=_auth_header(token_a),
    )
    assert failed_run_resp.status_code == 201
    failed_run_id = failed_run_resp.json()["id"]
    assert failed_run_resp.json()["status"] == "FAILED"

    retry_resp = ai_client.post(
        f"/api/ai/runs/{failed_run_id}/retry",
        json={"force_fail": False, "context": {"case": "retry-success"}},
        headers=_auth_header(token_a),
    )
    assert retry_resp.status_code == 200
    retry_run = retry_resp.json()
    assert retry_run["status"] == "SUCCEEDED"
    assert retry_run["retry_of_run_id"] == failed_run_id
    assert retry_run["retry_count"] == 1

    outputs_resp = ai_client.get(
        f"/api/ai/outputs?run_id={retry_run['id']}",
        headers=_auth_header(token_a),
    )
    assert outputs_resp.status_code == 200
    outputs = outputs_resp.json()
    assert len(outputs) == 1
    output_id = outputs[0]["id"]

    denied_resp = ai_client.get(f"/api/ai/outputs/{output_id}", headers=_auth_header(token_b))
    assert denied_resp.status_code == 404


def test_ai_model_governance_wp1_minimal_chain(ai_client: TestClient) -> None:
    tenant_id = _create_tenant(ai_client, "phase23-ai-governance")
    _bootstrap_admin(ai_client, tenant_id, "admin-gov", "admin-pass")
    token = _login(ai_client, tenant_id, "admin-gov", "admin-pass")

    create_model_resp = ai_client.post(
        "/api/ai/models",
        json={
            "model_key": "builtin:uav-assistant-lite",
            "provider": "builtin",
            "display_name": "uav-assistant-lite",
            "description": "phase23 governance model",
            "is_active": True,
        },
        headers=_auth_header(token),
    )
    assert create_model_resp.status_code == 201
    model_id = create_model_resp.json()["id"]

    create_version_resp = ai_client.post(
        f"/api/ai/models/{model_id}/versions",
        json={
            "version": "phase23.v1",
            "status": "DRAFT",
            "threshold_defaults": {"confidence_min": 0.8},
        },
        headers=_auth_header(token),
    )
    assert create_version_resp.status_code == 201
    version_id = create_version_resp.json()["id"]
    assert create_version_resp.json()["status"] == "DRAFT"

    promote_resp = ai_client.post(
        f"/api/ai/models/{model_id}/versions/{version_id}:promote",
        json={"target_status": "STABLE"},
        headers=_auth_header(token),
    )
    assert promote_resp.status_code == 200
    assert promote_resp.json()["status"] == "STABLE"

    versions_resp = ai_client.get(
        f"/api/ai/models/{model_id}/versions?status_filter=STABLE",
        headers=_auth_header(token),
    )
    assert versions_resp.status_code == 200
    versions = versions_resp.json()
    assert len(versions) == 1
    assert versions[0]["id"] == version_id

    job_resp = ai_client.post(
        "/api/ai/jobs",
        json={
            "job_type": "SUMMARY",
            "trigger_mode": "MANUAL",
            "model_version_id": version_id,
        },
        headers=_auth_header(token),
    )
    assert job_resp.status_code == 201
    body = job_resp.json()
    assert body["model_version_id"] == version_id
    assert body["model_provider"] == "builtin"
    assert body["model_name"] == "uav-assistant-lite"
    assert body["model_version"] == "phase23.v1"


def test_ai_rollout_policy_and_run_selection_priority(ai_client: TestClient) -> None:
    tenant_id = _create_tenant(ai_client, "phase23-ai-rollout")
    _bootstrap_admin(ai_client, tenant_id, "admin-rollout", "admin-pass")
    token = _login(ai_client, tenant_id, "admin-rollout", "admin-pass")

    model_resp = ai_client.post(
        "/api/ai/models",
        json={
            "model_key": "builtin:uav-assistant-lite",
            "provider": "builtin",
            "display_name": "uav-assistant-lite",
            "is_active": True,
        },
        headers=_auth_header(token),
    )
    assert model_resp.status_code == 201
    model_id = model_resp.json()["id"]

    stable_resp = ai_client.post(
        f"/api/ai/models/{model_id}/versions",
        json={
            "version": "phase23.rollout.v1",
            "status": "STABLE",
            "threshold_defaults": {"confidence_min": 0.8},
        },
        headers=_auth_header(token),
    )
    assert stable_resp.status_code == 201
    stable_id = stable_resp.json()["id"]

    canary_resp = ai_client.post(
        f"/api/ai/models/{model_id}/versions",
        json={
            "version": "phase23.rollout.v2",
            "status": "CANARY",
            "threshold_defaults": {"confidence_min": 0.7},
        },
        headers=_auth_header(token),
    )
    assert canary_resp.status_code == 201
    canary_id = canary_resp.json()["id"]

    policy_resp = ai_client.put(
        f"/api/ai/models/{model_id}/rollout-policy",
        json={
            "default_version_id": stable_id,
            "traffic_allocation": [
                {"version_id": stable_id, "weight": 90},
                {"version_id": canary_id, "weight": 10},
            ],
            "threshold_overrides": {"confidence_min": 0.75},
            "is_active": True,
        },
        headers=_auth_header(token),
    )
    assert policy_resp.status_code == 200
    policy_id = policy_resp.json()["id"]
    assert policy_resp.json()["default_version_id"] == stable_id

    policy_get_resp = ai_client.get(
        f"/api/ai/models/{model_id}/rollout-policy",
        headers=_auth_header(token),
    )
    assert policy_get_resp.status_code == 200
    policy_body = policy_get_resp.json()
    assert sum(int(item["weight"]) for item in policy_body["traffic_allocation"]) == 100

    job_resp = ai_client.post(
        "/api/ai/jobs",
        json={
            "job_type": "SUMMARY",
            "trigger_mode": "MANUAL",
            "model_version_id": stable_id,
        },
        headers=_auth_header(token),
    )
    assert job_resp.status_code == 201
    job_id = job_resp.json()["id"]

    forced_run_resp = ai_client.post(
        f"/api/ai/jobs/{job_id}/runs",
        json={
            "force_model_version_id": canary_id,
            "force_threshold_config": {"confidence_min": 0.72},
            "context": {"case": "manual-force"},
        },
        headers=_auth_header(token),
    )
    assert forced_run_resp.status_code == 201
    forced_run = forced_run_resp.json()
    assert forced_run["status"] == "SUCCEEDED"
    assert forced_run["metrics"]["selection_source"] == "MANUAL_FORCE"
    assert forced_run["metrics"]["model_version_id"] == canary_id
    assert forced_run["metrics"]["threshold_snapshot"]["confidence_min"] == 0.72

    outputs_resp = ai_client.get(
        f"/api/ai/outputs?run_id={forced_run['id']}",
        headers=_auth_header(token),
    )
    assert outputs_resp.status_code == 200
    outputs = outputs_resp.json()
    assert len(outputs) == 1
    output_id = outputs[0]["id"]
    assert outputs[0]["payload"]["model_selection"]["model_version_id"] == canary_id
    assert outputs[0]["payload"]["model_selection"]["policy_snapshot"]["policy_id"] == policy_id
    assert outputs[0]["payload"]["model_selection"]["threshold_snapshot"]["confidence_min"] == 0.72

    review_resp = ai_client.get(f"/api/ai/outputs/{output_id}/review", headers=_auth_header(token))
    assert review_resp.status_code == 200
    model_evidence = next(
        item for item in review_resp.json()["evidences"] if item["evidence_type"] == "MODEL_CONFIG"
    )
    assert model_evidence["payload"]["model_version_id"] == canary_id
    assert model_evidence["payload"]["policy_snapshot"]["policy_id"] == policy_id
    assert model_evidence["payload"]["threshold_config"]["confidence_min"] == 0.72

    bind_resp = ai_client.post(
        f"/api/ai/jobs/{job_id}:bind-model-version",
        json={"model_version_id": canary_id},
        headers=_auth_header(token),
    )
    assert bind_resp.status_code == 200
    assert bind_resp.json()["model_version_id"] == canary_id

    bound_run_resp = ai_client.post(
        f"/api/ai/jobs/{job_id}/runs",
        json={"context": {"case": "job-binding"}},
        headers=_auth_header(token),
    )
    assert bound_run_resp.status_code == 201
    bound_run = bound_run_resp.json()
    assert bound_run["status"] == "SUCCEEDED"
    assert bound_run["metrics"]["selection_source"] == "JOB_BINDING"
    assert bound_run["metrics"]["model_version_id"] == canary_id
    assert bound_run["metrics"]["threshold_snapshot"]["confidence_min"] == 0.8


def test_ai_evaluation_rollback_and_schedule_tick(ai_client: TestClient) -> None:
    tenant_id = _create_tenant(ai_client, "phase23-ai-eval")
    _bootstrap_admin(ai_client, tenant_id, "admin-eval", "admin-pass")
    token = _login(ai_client, tenant_id, "admin-eval", "admin-pass")

    model_resp = ai_client.post(
        "/api/ai/models",
        json={
            "model_key": "builtin:uav-assistant-lite",
            "provider": "builtin",
            "display_name": "uav-assistant-lite",
        },
        headers=_auth_header(token),
    )
    assert model_resp.status_code == 201
    model_id = model_resp.json()["id"]

    stable_resp = ai_client.post(
        f"/api/ai/models/{model_id}/versions",
        json={"version": "phase23.eval.v1", "status": "STABLE", "threshold_defaults": {"confidence_min": 0.8}},
        headers=_auth_header(token),
    )
    assert stable_resp.status_code == 201
    stable_id = stable_resp.json()["id"]

    canary_resp = ai_client.post(
        f"/api/ai/models/{model_id}/versions",
        json={"version": "phase23.eval.v2", "status": "CANARY", "threshold_defaults": {"confidence_min": 0.7}},
        headers=_auth_header(token),
    )
    assert canary_resp.status_code == 201
    canary_id = canary_resp.json()["id"]

    set_policy_resp = ai_client.put(
        f"/api/ai/models/{model_id}/rollout-policy",
        json={
            "default_version_id": canary_id,
            "traffic_allocation": [
                {"version_id": stable_id, "weight": 40},
                {"version_id": canary_id, "weight": 60},
            ],
            "threshold_overrides": {"confidence_min": 0.75},
            "is_active": True,
        },
        headers=_auth_header(token),
    )
    assert set_policy_resp.status_code == 200

    job_resp = ai_client.post(
        "/api/ai/jobs",
        json={
            "job_type": "SUMMARY",
            "trigger_mode": "NEAR_REALTIME",
            "model_version_id": canary_id,
        },
        headers=_auth_header(token),
    )
    assert job_resp.status_code == 201
    job_id = job_resp.json()["id"]

    tick_first = ai_client.post(
        "/api/ai/jobs:schedule-tick",
        json={"window_key": "2026-02-27T16:00Z", "job_ids": [job_id], "max_jobs": 10},
        headers=_auth_header(token),
    )
    assert tick_first.status_code == 200
    first_body = tick_first.json()
    assert first_body["triggered_jobs"] == 1
    assert first_body["skipped_jobs"] == 0

    tick_second = ai_client.post(
        "/api/ai/jobs:schedule-tick",
        json={"window_key": "2026-02-27T16:00Z", "job_ids": [job_id], "max_jobs": 10},
        headers=_auth_header(token),
    )
    assert tick_second.status_code == 200
    second_body = tick_second.json()
    assert second_body["triggered_jobs"] == 0
    assert second_body["skipped_jobs"] == 1

    force_run_resp = ai_client.post(
        f"/api/ai/jobs/{job_id}/runs",
        json={"force_model_version_id": stable_id, "context": {"case": "eval-compare"}},
        headers=_auth_header(token),
    )
    assert force_run_resp.status_code == 201
    assert force_run_resp.json()["status"] == "SUCCEEDED"

    recompute_resp = ai_client.post(
        "/api/ai/evaluations:recompute",
        json={"job_id": job_id},
        headers=_auth_header(token),
    )
    assert recompute_resp.status_code == 200
    summaries = recompute_resp.json()
    assert len(summaries) >= 2
    summary_by_version = {item["model_version_id"]: item for item in summaries}
    assert stable_id in summary_by_version
    assert canary_id in summary_by_version

    compare_resp = ai_client.get(
        f"/api/ai/evaluations/compare?left_version_id={stable_id}&right_version_id={canary_id}&job_id={job_id}",
        headers=_auth_header(token),
    )
    assert compare_resp.status_code == 200
    compare_body = compare_resp.json()
    assert compare_body["left"]["model_version_id"] == stable_id
    assert compare_body["right"]["model_version_id"] == canary_id

    rollback_resp = ai_client.post(
        f"/api/ai/models/{model_id}/rollout-policy:rollback",
        json={"target_version_id": stable_id, "reason": "canary quality drop"},
        headers=_auth_header(token),
    )
    assert rollback_resp.status_code == 200
    assert rollback_resp.json()["default_version_id"] == stable_id
    assert rollback_resp.json()["traffic_allocation"] == [{"version_id": stable_id, "weight": 100}]
