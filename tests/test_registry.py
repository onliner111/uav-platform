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
def registry_client(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Generator[TestClient, None, None]:
    db_path = tmp_path / "registry_test.db"
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


def test_registry_tenant_isolation(registry_client: TestClient) -> None:
    tenant_a = _create_tenant(registry_client, "registry-tenant-a")
    tenant_b = _create_tenant(registry_client, "registry-tenant-b")
    _bootstrap_admin(registry_client, tenant_a, "admin_a", "pass-a")
    _bootstrap_admin(registry_client, tenant_b, "admin_b", "pass-b")
    token_a = _login(registry_client, tenant_a, "admin_a", "pass-a")
    token_b = _login(registry_client, tenant_b, "admin_b", "pass-b")

    create_resp = registry_client.post(
        "/api/registry/drones",
        json={
            "name": "drone-a1",
            "vendor": "FAKE",
            "capabilities": {"camera": True},
        },
        headers=_auth_header(token_a),
    )
    assert create_resp.status_code == 201
    drone_id = create_resp.json()["id"]

    cross_get = registry_client.get(
        f"/api/registry/drones/{drone_id}",
        headers=_auth_header(token_b),
    )
    assert cross_get.status_code == 404

    cross_update = registry_client.patch(
        f"/api/registry/drones/{drone_id}",
        json={"name": "spoofed"},
        headers=_auth_header(token_b),
    )
    assert cross_update.status_code == 404

    cross_delete = registry_client.delete(
        f"/api/registry/drones/{drone_id}",
        headers=_auth_header(token_b),
    )
    assert cross_delete.status_code == 404

    list_b = registry_client.get("/api/registry/drones", headers=_auth_header(token_b))
    assert list_b.status_code == 200
    assert list_b.json() == []


def test_registry_emits_registered_and_updated_events(registry_client: TestClient) -> None:
    tenant_id = _create_tenant(registry_client, "registry-events-tenant")
    _bootstrap_admin(registry_client, tenant_id, "admin", "pass")
    token = _login(registry_client, tenant_id, "admin", "pass")

    create_resp = registry_client.post(
        "/api/registry/drones",
        json={"name": "drone-evt", "vendor": "FAKE", "capabilities": {"rth": True}},
        headers=_auth_header(token),
    )
    assert create_resp.status_code == 201
    drone_id = create_resp.json()["id"]

    update_resp = registry_client.patch(
        f"/api/registry/drones/{drone_id}",
        json={"capabilities": {"rth": True, "vision": True}},
        headers=_auth_header(token),
    )
    assert update_resp.status_code == 200

    with Session(db.engine) as session:
        statement = select(EventRecord).where(EventRecord.tenant_id == tenant_id)
        rows = list(session.exec(statement).all())

    filtered_rows = [row for row in rows if row.payload.get("drone_id") == drone_id]
    event_types = {row.event_type for row in filtered_rows}
    assert "drone.registered" in event_types
    assert "drone.updated" in event_types
