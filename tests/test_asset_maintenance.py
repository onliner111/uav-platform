from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine, select

from app import main as app_main
from app.domain.models import EventRecord
from app.infra import audit, db, events


@pytest.fixture()
def maintenance_client(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Generator[TestClient, None, None]:
    db_path = tmp_path / "asset_maintenance_test.db"
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


def _create_asset(client: TestClient, token: str, code: str) -> str:
    response = client.post(
        "/api/assets",
        json={"asset_type": "PAYLOAD", "asset_code": code, "name": f"asset-{code}"},
        headers=_auth_header(token),
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_maintenance_workorder_workflow_and_tenant_isolation(maintenance_client: TestClient) -> None:
    tenant_a = _create_tenant(maintenance_client, "maint-tenant-a")
    tenant_b = _create_tenant(maintenance_client, "maint-tenant-b")
    _bootstrap_admin(maintenance_client, tenant_a, "admin_a", "pass-a")
    _bootstrap_admin(maintenance_client, tenant_b, "admin_b", "pass-b")
    token_a = _login(maintenance_client, tenant_a, "admin_a", "pass-a")
    token_b = _login(maintenance_client, tenant_b, "admin_b", "pass-b")

    asset_id = _create_asset(maintenance_client, token_a, "MNT-A1")

    create_resp = maintenance_client.post(
        "/api/assets/maintenance/workorders",
        json={
            "asset_id": asset_id,
            "title": "replace payload module",
            "description": "wp3 flow check",
            "priority": 3,
            "note": "created for workflow test",
        },
        headers=_auth_header(token_a),
    )
    assert create_resp.status_code == 201
    workorder_id = create_resp.json()["id"]
    assert create_resp.json()["status"] == "OPEN"

    transition_resp = maintenance_client.post(
        f"/api/assets/maintenance/workorders/{workorder_id}/transition",
        json={"status": "IN_PROGRESS", "note": "start fixing"},
        headers=_auth_header(token_a),
    )
    assert transition_resp.status_code == 200
    assert transition_resp.json()["status"] == "IN_PROGRESS"

    close_resp = maintenance_client.post(
        f"/api/assets/maintenance/workorders/{workorder_id}/close",
        json={"note": "fixed and verified"},
        headers=_auth_header(token_a),
    )
    assert close_resp.status_code == 200
    assert close_resp.json()["status"] == "CLOSED"

    history_resp = maintenance_client.get(
        f"/api/assets/maintenance/workorders/{workorder_id}/history",
        headers=_auth_header(token_a),
    )
    assert history_resp.status_code == 200
    actions = [item["action"] for item in history_resp.json()]
    assert actions == ["created", "status_changed", "closed"]

    cross_get = maintenance_client.get(
        f"/api/assets/maintenance/workorders/{workorder_id}",
        headers=_auth_header(token_b),
    )
    assert cross_get.status_code == 404

    cross_history = maintenance_client.get(
        f"/api/assets/maintenance/workorders/{workorder_id}/history",
        headers=_auth_header(token_b),
    )
    assert cross_history.status_code == 404


def test_maintenance_workorder_events_and_conflicts(maintenance_client: TestClient) -> None:
    tenant_id = _create_tenant(maintenance_client, "maint-events-tenant")
    _bootstrap_admin(maintenance_client, tenant_id, "admin", "pass")
    token = _login(maintenance_client, tenant_id, "admin", "pass")
    asset_id = _create_asset(maintenance_client, token, "MNT-EVT")

    create_resp = maintenance_client.post(
        "/api/assets/maintenance/workorders",
        json={"asset_id": asset_id, "title": "event test", "priority": 4},
        headers=_auth_header(token),
    )
    assert create_resp.status_code == 201
    workorder_id = create_resp.json()["id"]

    wrong_transition = maintenance_client.post(
        f"/api/assets/maintenance/workorders/{workorder_id}/transition",
        json={"status": "CLOSED", "note": "should fail"},
        headers=_auth_header(token),
    )
    assert wrong_transition.status_code == 409

    ok_transition = maintenance_client.post(
        f"/api/assets/maintenance/workorders/{workorder_id}/transition",
        json={"status": "IN_PROGRESS", "note": "in progress"},
        headers=_auth_header(token),
    )
    assert ok_transition.status_code == 200

    close_resp = maintenance_client.post(
        f"/api/assets/maintenance/workorders/{workorder_id}/close",
        json={"note": "done"},
        headers=_auth_header(token),
    )
    assert close_resp.status_code == 200

    close_again = maintenance_client.post(
        f"/api/assets/maintenance/workorders/{workorder_id}/close",
        json={"note": "done-again"},
        headers=_auth_header(token),
    )
    assert close_again.status_code == 409

    with Session(db.engine) as session:
        statement = select(EventRecord).where(EventRecord.tenant_id == tenant_id)
        rows = list(session.exec(statement).all())
    event_types = {row.event_type for row in rows if row.event_type.startswith("asset.maintenance_workorder")}
    assert "asset.maintenance_workorder.created" in event_types
    assert "asset.maintenance_workorder.status_changed" in event_types
    assert "asset.maintenance_workorder.closed" in event_types
