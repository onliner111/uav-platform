from __future__ import annotations

import json
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlmodel import SQLModel, create_engine

from app import main as app_main
from app.infra import audit, db, events
from app.services.tenant_purge_service import TENANT_PURGE_CONFIRM_PHRASE


@pytest.fixture()
def tenant_purge_execute_client(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Generator[TestClient, None, None]:
    db_path = tmp_path / "tenant_purge_execute_test.db"
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
    monkeypatch.chdir(tmp_path)

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


def _create_drone(client: TestClient, token: str, name: str) -> str:
    response = client.post(
        "/api/registry/drones",
        json={"name": name, "vendor": "FAKE", "capabilities": {"camera": True}},
        headers=_auth_header(token),
    )
    assert response.status_code == 201
    return response.json()["id"]


def _create_mission(client: TestClient, token: str, name: str, drone_id: str) -> str:
    response = client.post(
        "/api/mission/missions",
        json={
            "name": name,
            "drone_id": drone_id,
            "type": "POINT_TASK",
            "payload": {},
            "constraints": {},
        },
        headers=_auth_header(token),
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_tenant_purge_execute_requires_confirmation_and_deletes_data(
    tenant_purge_execute_client: TestClient,
) -> None:
    tenant_a = _create_tenant(tenant_purge_execute_client, "purge-exec-a")
    tenant_b = _create_tenant(tenant_purge_execute_client, "purge-exec-b")
    _bootstrap_admin(tenant_purge_execute_client, tenant_a, "admin_a", "pass-a")
    _bootstrap_admin(tenant_purge_execute_client, tenant_b, "admin_b", "pass-b")
    token_a = _login(tenant_purge_execute_client, tenant_a, "admin_a", "pass-a")
    token_b = _login(tenant_purge_execute_client, tenant_b, "admin_b", "pass-b")

    drone_a = _create_drone(tenant_purge_execute_client, token_a, "drone-a")
    mission_a = _create_mission(tenant_purge_execute_client, token_a, "mission-a", drone_a)
    drone_b = _create_drone(tenant_purge_execute_client, token_b, "drone-b")
    _create_mission(tenant_purge_execute_client, token_b, "mission-b", drone_b)

    dry_run_resp = tenant_purge_execute_client.post(
        f"/api/tenants/{tenant_a}/purge:dry_run",
        headers=_auth_header(token_a),
    )
    assert dry_run_resp.status_code == 200
    dry_run_body = dry_run_resp.json()
    dry_run_id = dry_run_body["dry_run_id"]

    missing_confirmation = tenant_purge_execute_client.post(
        f"/api/tenants/{tenant_a}/purge",
        json={"dry_run_id": dry_run_id, "mode": "hard"},
        headers=_auth_header(token_a),
    )
    assert missing_confirmation.status_code == 409

    execute_resp = tenant_purge_execute_client.post(
        f"/api/tenants/{tenant_a}/purge",
        json={
            "dry_run_id": dry_run_id,
            "confirm_phrase": TENANT_PURGE_CONFIRM_PHRASE,
            "mode": "hard",
        },
        headers=_auth_header(token_a),
    )
    assert execute_resp.status_code == 200
    execute_body = execute_resp.json()
    assert execute_body["status"] == "completed"
    assert execute_body["deleted_rows"] > 0
    assert all(count == 0 for count in execute_body["post_delete_counts"].values())

    report_path = Path(execute_body["report_path"])
    assert report_path.exists()
    report_body = json.loads(report_path.read_text(encoding="utf-8"))
    assert report_body["dry_run_id"] == dry_run_id
    assert report_body["status"] == "completed"
    assert all(value == 0 for value in report_body["post_delete_counts"].values())

    get_deleted_mission = tenant_purge_execute_client.get(
        f"/api/mission/missions/{mission_a}",
        headers=_auth_header(token_a),
    )
    assert get_deleted_mission.status_code == 404

    overview_a = tenant_purge_execute_client.get(
        "/api/reporting/overview",
        headers=_auth_header(token_a),
    )
    overview_b = tenant_purge_execute_client.get(
        "/api/reporting/overview",
        headers=_auth_header(token_b),
    )
    assert overview_a.status_code == 200
    assert overview_b.status_code == 200
    assert overview_a.json()["missions_total"] == 0
    assert overview_b.json()["missions_total"] == 1

    status_resp = tenant_purge_execute_client.get(
        f"/api/tenants/{tenant_a}/purge/{execute_body['purge_id']}",
        headers=_auth_header(token_a),
    )
    assert status_resp.status_code == 200
    assert status_resp.json()["purge_id"] == execute_body["purge_id"]

    status_cross_tenant = tenant_purge_execute_client.get(
        f"/api/tenants/{tenant_a}/purge/{execute_body['purge_id']}",
        headers=_auth_header(token_b),
    )
    assert status_cross_tenant.status_code == 404
