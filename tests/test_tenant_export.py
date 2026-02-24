from __future__ import annotations

import json
from collections.abc import Generator
from pathlib import Path
from zipfile import ZipFile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlmodel import SQLModel, create_engine

from app import main as app_main
from app.infra import audit, db, events


@pytest.fixture()
def tenant_export_client(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Generator[TestClient, None, None]:
    db_path = tmp_path / "tenant_export_test.db"
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


def test_tenant_export_contains_only_requested_tenant_data(tenant_export_client: TestClient) -> None:
    tenant_a = _create_tenant(tenant_export_client, "export-tenant-a")
    tenant_b = _create_tenant(tenant_export_client, "export-tenant-b")
    _bootstrap_admin(tenant_export_client, tenant_a, "admin_a", "pass-a")
    _bootstrap_admin(tenant_export_client, tenant_b, "admin_b", "pass-b")

    token_a = _login(tenant_export_client, tenant_a, "admin_a", "pass-a")
    token_b = _login(tenant_export_client, tenant_b, "admin_b", "pass-b")

    _create_user(tenant_export_client, token_a, "user_a", "user-pass-a")
    _create_user(tenant_export_client, token_b, "user_b", "user-pass-b")
    _create_drone(tenant_export_client, token_a, "drone-a")
    _create_drone(tenant_export_client, token_b, "drone-b")

    export_resp = tenant_export_client.post(
        f"/api/tenants/{tenant_a}/export?include_zip=true",
        headers=_auth_header(token_a),
    )
    assert export_resp.status_code == 201
    export_body = export_resp.json()

    manifest_path = Path(export_body["manifest_path"])
    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["tenant_id"] == tenant_a
    assert "permissions" in manifest["global_tables_skipped"]

    zip_path = Path(export_body["zip_path"])
    assert zip_path.exists()
    with ZipFile(zip_path, "r") as archive:
        names = set(archive.namelist())
        assert "manifest.json" in names
        assert "tables/users.jsonl" in names

    export_dir = manifest_path.parent
    users_file = export_dir / "tables" / "users.jsonl"
    assert users_file.exists()
    user_rows = [
        json.loads(line)
        for line in users_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert user_rows
    assert all(row["tenant_id"] == tenant_a for row in user_rows)
    assert all(row["tenant_id"] != tenant_b for row in user_rows)

    drones_file = export_dir / "tables" / "drones.jsonl"
    assert drones_file.exists()
    drone_rows = [
        json.loads(line)
        for line in drones_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert drone_rows
    assert all(row["tenant_id"] == tenant_a for row in drone_rows)


def test_tenant_export_cross_tenant_access_returns_404(tenant_export_client: TestClient) -> None:
    tenant_a = _create_tenant(tenant_export_client, "export-cross-a")
    tenant_b = _create_tenant(tenant_export_client, "export-cross-b")
    _bootstrap_admin(tenant_export_client, tenant_a, "admin_a", "pass-a")
    _bootstrap_admin(tenant_export_client, tenant_b, "admin_b", "pass-b")

    token_a = _login(tenant_export_client, tenant_a, "admin_a", "pass-a")
    token_b = _login(tenant_export_client, tenant_b, "admin_b", "pass-b")

    create_cross_resp = tenant_export_client.post(
        f"/api/tenants/{tenant_a}/export",
        headers=_auth_header(token_b),
    )
    assert create_cross_resp.status_code == 404

    create_resp = tenant_export_client.post(
        f"/api/tenants/{tenant_a}/export",
        headers=_auth_header(token_a),
    )
    assert create_resp.status_code == 201
    export_id = create_resp.json()["export_id"]

    status_cross_resp = tenant_export_client.get(
        f"/api/tenants/{tenant_a}/export/{export_id}",
        headers=_auth_header(token_b),
    )
    assert status_cross_resp.status_code == 404

    download_cross_resp = tenant_export_client.get(
        f"/api/tenants/{tenant_a}/export/{export_id}/download",
        headers=_auth_header(token_b),
    )
    assert download_cross_resp.status_code == 404


def test_tenant_export_is_admin_only(tenant_export_client: TestClient) -> None:
    tenant_id = _create_tenant(tenant_export_client, "export-admin-only")
    _bootstrap_admin(tenant_export_client, tenant_id, "admin", "admin-pass")
    admin_token = _login(tenant_export_client, tenant_id, "admin", "admin-pass")

    _create_user(tenant_export_client, admin_token, "operator", "operator-pass")
    operator_token = _login(tenant_export_client, tenant_id, "operator", "operator-pass")

    export_resp = tenant_export_client.post(
        f"/api/tenants/{tenant_id}/export",
        headers=_auth_header(operator_token),
    )
    assert export_resp.status_code == 403
