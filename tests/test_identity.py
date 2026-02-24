from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel, create_engine

from app import main as app_main
from app.domain.models import UserRole
from app.infra import audit, db, events


@pytest.fixture()
def identity_client(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Generator[TestClient, None, None]:
    db_path = tmp_path / "identity_test.db"
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


def test_identity_tenant_isolation(identity_client: TestClient) -> None:
    tenant_a = _create_tenant(identity_client, "tenant-a")
    tenant_b = _create_tenant(identity_client, "tenant-b")
    _bootstrap_admin(identity_client, tenant_a, "admin_a", "pass-a")
    _bootstrap_admin(identity_client, tenant_b, "admin_b", "pass-b")

    token_a = _login(identity_client, tenant_a, "admin_a", "pass-a")
    token_b = _login(identity_client, tenant_b, "admin_b", "pass-b")

    create_user_resp = identity_client.post(
        "/api/identity/users",
        json={"username": "alice", "password": "alice-pass", "is_active": True},
        headers=_auth_header(token_a),
    )
    assert create_user_resp.status_code == 201
    alice_id = create_user_resp.json()["id"]

    cross_tenant_resp = identity_client.get(
        f"/api/identity/users/{alice_id}",
        headers=_auth_header(token_b),
    )
    assert cross_tenant_resp.status_code == 404


def test_identity_permission_denied(identity_client: TestClient) -> None:
    tenant_id = _create_tenant(identity_client, "tenant-perm")
    _bootstrap_admin(identity_client, tenant_id, "admin", "admin-pass")
    admin_token = _login(identity_client, tenant_id, "admin", "admin-pass")

    role_resp = identity_client.post(
        "/api/identity/roles",
        json={"name": "viewer", "description": "no permissions"},
        headers=_auth_header(admin_token),
    )
    assert role_resp.status_code == 201
    role_id = role_resp.json()["id"]

    bob_resp = identity_client.post(
        "/api/identity/users",
        json={"username": "bob", "password": "bob-pass", "is_active": True},
        headers=_auth_header(admin_token),
    )
    assert bob_resp.status_code == 201
    bob_id = bob_resp.json()["id"]

    bind_resp = identity_client.post(
        f"/api/identity/users/{bob_id}/roles/{role_id}",
        headers=_auth_header(admin_token),
    )
    assert bind_resp.status_code == 204

    bob_token = _login(identity_client, tenant_id, "bob", "bob-pass")
    forbidden_resp = identity_client.get("/api/identity/users", headers=_auth_header(bob_token))
    assert forbidden_resp.status_code == 403


def test_identity_cross_tenant_bind_unbind_returns_404(identity_client: TestClient) -> None:
    tenant_a = _create_tenant(identity_client, "tenant-404-a")
    tenant_b = _create_tenant(identity_client, "tenant-404-b")
    _bootstrap_admin(identity_client, tenant_a, "admin_a", "pass-a")
    _bootstrap_admin(identity_client, tenant_b, "admin_b", "pass-b")

    token_a = _login(identity_client, tenant_a, "admin_a", "pass-a")
    token_b = _login(identity_client, tenant_b, "admin_b", "pass-b")

    user_a_resp = identity_client.post(
        "/api/identity/users",
        json={"username": "alice_a", "password": "alice-pass", "is_active": True},
        headers=_auth_header(token_a),
    )
    assert user_a_resp.status_code == 201
    user_a_id = user_a_resp.json()["id"]

    role_a_resp = identity_client.post(
        "/api/identity/roles",
        json={"name": "viewer_a", "description": "tenant-a role"},
        headers=_auth_header(token_a),
    )
    assert role_a_resp.status_code == 201
    role_a_id = role_a_resp.json()["id"]

    role_b_resp = identity_client.post(
        "/api/identity/roles",
        json={"name": "viewer_b", "description": "tenant-b role"},
        headers=_auth_header(token_b),
    )
    assert role_b_resp.status_code == 201
    role_b_id = role_b_resp.json()["id"]

    cross_bind_resp = identity_client.post(
        f"/api/identity/users/{user_a_id}/roles/{role_b_id}",
        headers=_auth_header(token_a),
    )
    assert cross_bind_resp.status_code == 404

    bind_resp = identity_client.post(
        f"/api/identity/users/{user_a_id}/roles/{role_a_id}",
        headers=_auth_header(token_a),
    )
    assert bind_resp.status_code == 204

    cross_unbind_resp = identity_client.delete(
        f"/api/identity/users/{user_a_id}/roles/{role_a_id}",
        headers=_auth_header(token_b),
    )
    assert cross_unbind_resp.status_code == 404


def test_identity_user_roles_composite_fk_enforced(identity_client: TestClient) -> None:
    tenant_a = _create_tenant(identity_client, "tenant-fk-a")
    tenant_b = _create_tenant(identity_client, "tenant-fk-b")
    _bootstrap_admin(identity_client, tenant_a, "admin_fk_a", "pass-a")
    _bootstrap_admin(identity_client, tenant_b, "admin_fk_b", "pass-b")

    token_a = _login(identity_client, tenant_a, "admin_fk_a", "pass-a")
    token_b = _login(identity_client, tenant_b, "admin_fk_b", "pass-b")

    user_a_resp = identity_client.post(
        "/api/identity/users",
        json={"username": "charlie_a", "password": "charlie-pass", "is_active": True},
        headers=_auth_header(token_a),
    )
    assert user_a_resp.status_code == 201
    user_a_id = user_a_resp.json()["id"]

    role_a_resp = identity_client.post(
        "/api/identity/roles",
        json={"name": "ops_a", "description": "tenant-a role"},
        headers=_auth_header(token_a),
    )
    assert role_a_resp.status_code == 201
    role_a_id = role_a_resp.json()["id"]

    role_b_resp = identity_client.post(
        "/api/identity/roles",
        json={"name": "ops_b", "description": "tenant-b role"},
        headers=_auth_header(token_b),
    )
    assert role_b_resp.status_code == 201
    role_b_id = role_b_resp.json()["id"]

    with Session(db.get_engine(), expire_on_commit=False) as session:
        session.add(UserRole(tenant_id=tenant_a, user_id=user_a_id, role_id=role_b_id))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        session.add(UserRole(tenant_id=tenant_a, user_id=user_a_id, role_id=role_a_id))
        session.commit()
