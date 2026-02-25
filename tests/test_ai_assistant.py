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
