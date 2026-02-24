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
def tenant_purge_client(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Generator[TestClient, None, None]:
    db_path = tmp_path / "tenant_purge_dry_run_test.db"
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


def _create_user(client: TestClient, admin_token: str, username: str, password: str) -> str:
    response = client.post(
        "/api/identity/users",
        json={"username": username, "password": password, "is_active": True},
        headers=_auth_header(admin_token),
    )
    assert response.status_code == 201
    return response.json()["id"]


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


def test_tenant_purge_dry_run_returns_plan_and_counts(tenant_purge_client: TestClient) -> None:
    tenant_id = _create_tenant(tenant_purge_client, "purge-dry-run")
    _bootstrap_admin(tenant_purge_client, tenant_id, "admin", "admin-pass")
    token = _login(tenant_purge_client, tenant_id, "admin", "admin-pass")

    drone_id = _create_drone(tenant_purge_client, token, "drone-a")
    _create_mission(tenant_purge_client, token, "mission-a", drone_id)

    response = tenant_purge_client.post(
        f"/api/tenants/{tenant_id}/purge:dry_run",
        headers=_auth_header(token),
    )
    assert response.status_code == 200
    body = response.json()

    assert body["status"] == "dry_run_ready"
    assert body["estimated_rows"] > 0
    assert body["counts"]["missions"] >= 1
    assert body["counts"]["drones"] >= 1
    assert body["confirm_token"]
    assert Path(body["dry_run_path"]).exists()

    plan = body["plan"]
    assert "missions" in plan
    assert "drones" in plan
    assert plan.index("missions") < plan.index("drones")


def test_tenant_purge_dry_run_cross_tenant_returns_404(tenant_purge_client: TestClient) -> None:
    tenant_a = _create_tenant(tenant_purge_client, "purge-cross-a")
    tenant_b = _create_tenant(tenant_purge_client, "purge-cross-b")
    _bootstrap_admin(tenant_purge_client, tenant_a, "admin_a", "pass-a")
    _bootstrap_admin(tenant_purge_client, tenant_b, "admin_b", "pass-b")
    token_b = _login(tenant_purge_client, tenant_b, "admin_b", "pass-b")

    response = tenant_purge_client.post(
        f"/api/tenants/{tenant_a}/purge:dry_run",
        headers=_auth_header(token_b),
    )
    assert response.status_code == 404


def test_tenant_purge_dry_run_is_admin_only(tenant_purge_client: TestClient) -> None:
    tenant_id = _create_tenant(tenant_purge_client, "purge-admin-only")
    _bootstrap_admin(tenant_purge_client, tenant_id, "admin", "admin-pass")
    admin_token = _login(tenant_purge_client, tenant_id, "admin", "admin-pass")
    _create_user(tenant_purge_client, admin_token, "operator", "operator-pass")
    operator_token = _login(tenant_purge_client, tenant_id, "operator", "operator-pass")

    response = tenant_purge_client.post(
        f"/api/tenants/{tenant_id}/purge:dry_run",
        headers=_auth_header(operator_token),
    )
    assert response.status_code == 403
