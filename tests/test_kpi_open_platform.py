from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlmodel import SQLModel, create_engine

from app import main as app_main
from app.infra import audit, db, events


@pytest.fixture()
def platform_client(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Generator[TestClient, None, None]:
    db_path = tmp_path / "phase15_test.db"
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
        json={"name": name, "category": "phase15", "description": "phase15", "is_active": True},
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
            "status": "DONE",
        },
        headers=_auth_header(token),
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_kpi_snapshot_and_heatmap(platform_client: TestClient) -> None:
    tenant_id = _create_tenant(platform_client, "phase15-kpi")
    _bootstrap_admin(platform_client, tenant_id, "admin", "admin-pass")
    token = _login(platform_client, tenant_id, "admin", "admin-pass")

    template_id = _create_template(platform_client, token, "phase15-template")
    task_id = _create_task(platform_client, token, template_id, "phase15-task")

    obs_resp = platform_client.post(
        f"/api/inspection/tasks/{task_id}/observations",
        json={
            "position_lat": 30.5801,
            "position_lon": 114.3001,
            "alt_m": 48.0,
            "item_code": "P15-A",
            "severity": 2,
            "note": "phase15 observation",
            "confidence": 0.9,
        },
        headers=_auth_header(token),
    )
    assert obs_resp.status_code == 201

    now = datetime.now(UTC)
    ingest_1 = platform_client.post(
        "/api/telemetry/ingest",
        json={
            "tenant_id": "spoofed",
            "drone_id": "phase15-drone-1",
            "ts": (now - timedelta(minutes=3)).isoformat(),
            "position": {"lat": 30.5800, "lon": 114.3000, "alt_m": 100.0},
            "battery": {"percent": 85.0},
            "link": {"latency_ms": 120},
            "mode": "AUTO",
            "health": {},
        },
        headers=_auth_header(token),
    )
    assert ingest_1.status_code == 200
    ingest_2 = platform_client.post(
        "/api/telemetry/ingest",
        json={
            "tenant_id": "spoofed",
            "drone_id": "phase15-drone-1",
            "ts": now.isoformat(),
            "position": {"lat": 30.5820, "lon": 114.3050, "alt_m": 100.0},
            "battery": {"percent": 80.0},
            "link": {"latency_ms": 130},
            "mode": "AUTO",
            "health": {},
        },
        headers=_auth_header(token),
    )
    assert ingest_2.status_code == 200

    recompute_resp = platform_client.post(
        "/api/kpi/snapshots/recompute",
        json={
            "from_ts": (now - timedelta(days=1)).isoformat(),
            "to_ts": (now + timedelta(days=1)).isoformat(),
            "window_type": "CUSTOM",
        },
        headers=_auth_header(token),
    )
    assert recompute_resp.status_code == 201
    metrics = recompute_resp.json()["metrics"]
    assert metrics["outcomes_total"] >= 1
    assert metrics["flight_mileage_km"] > 0

    heatmap_resp = platform_client.get(
        "/api/kpi/heatmap?source=OUTCOME",
        headers=_auth_header(token),
    )
    assert heatmap_resp.status_code == 200
    assert len(heatmap_resp.json()) >= 1

    export_resp = platform_client.post(
        "/api/kpi/governance/export",
        json={"title": "Phase15 KPI Report", "window_type": "MONTHLY"},
        headers=_auth_header(token),
    )
    assert export_resp.status_code == 200
    report_path = Path(export_resp.json()["file_path"])
    assert report_path.exists()


def test_open_platform_signature_and_webhook(platform_client: TestClient) -> None:
    tenant_id = _create_tenant(platform_client, "phase15-open")
    _bootstrap_admin(platform_client, tenant_id, "admin", "admin-pass")
    token = _login(platform_client, tenant_id, "admin", "admin-pass")

    credential_resp = platform_client.post(
        "/api/open-platform/credentials",
        json={"key_id": "phase15-key"},
        headers=_auth_header(token),
    )
    assert credential_resp.status_code == 201
    credential = credential_resp.json()

    webhook_resp = platform_client.post(
        "/api/open-platform/webhooks",
        json={
            "name": "phase15-hook",
            "endpoint_url": "https://external.example/hook",
            "event_type": "workorder.upsert",
            "credential_id": credential["id"],
        },
        headers=_auth_header(token),
    )
    assert webhook_resp.status_code == 201
    endpoint_id = webhook_resp.json()["id"]

    dispatch_resp = platform_client.post(
        f"/api/open-platform/webhooks/{endpoint_id}/dispatch-test",
        json={"payload": {"ticket_id": "WO-001"}},
        headers=_auth_header(token),
    )
    assert dispatch_resp.status_code == 200
    assert dispatch_resp.json()["status"] == "SENT"
    assert dispatch_resp.json()["signature"] is not None

    ingress_payload = {"event_type": "workorder.upsert", "payload": {"ticket_id": "WO-001"}}
    raw_body = json.dumps(ingress_payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    signature = hmac.new(
        credential["signing_secret"].encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()

    ingest_ok = platform_client.post(
        "/api/open-platform/adapters/events/ingest",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-Open-Key-Id": credential["key_id"],
            "X-Open-Api-Key": credential["api_key"],
            "X-Open-Signature": signature,
        },
    )
    assert ingest_ok.status_code == 201
    assert ingest_ok.json()["signature_valid"] is True
    assert ingest_ok.json()["status"] == "ACCEPTED"

    ingest_bad = platform_client.post(
        "/api/open-platform/adapters/events/ingest",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-Open-Key-Id": credential["key_id"],
            "X-Open-Api-Key": credential["api_key"],
            "X-Open-Signature": "bad-signature",
        },
    )
    assert ingest_bad.status_code == 401

    events_resp = platform_client.get("/api/open-platform/adapters/events", headers=_auth_header(token))
    assert events_resp.status_code == 200
    statuses = {item["status"] for item in events_resp.json()}
    assert "ACCEPTED" in statuses
    assert "REJECTED" in statuses
