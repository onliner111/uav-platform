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
def ui_client(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Generator[TestClient, None, None]:
    db_path = tmp_path / "ui_console_test.db"
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


def _login_token(client: TestClient, tenant_id: str, username: str, password: str) -> str:
    response = client.post(
        "/api/identity/dev-login",
        json={"tenant_id": tenant_id, "username": username, "password": password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_ui_login_session_and_logout_flow(ui_client: TestClient) -> None:
    tenant_id = _create_tenant(ui_client, "ui-flow-tenant")
    _bootstrap_admin(ui_client, tenant_id, "ui_admin", "ui-pass")

    login_page = ui_client.get("/ui/login?next=/ui/console")
    assert login_page.status_code == 200
    csrf_token = ui_client.cookies.get("uav_ui_csrf")
    assert csrf_token

    login_resp = ui_client.post(
        "/ui/login",
        data={
            "tenant_id": tenant_id,
            "username": "ui_admin",
            "password": "ui-pass",
            "csrf_token": csrf_token,
            "next": "/ui/console",
        },
        follow_redirects=False,
    )
    assert login_resp.status_code == 303
    assert login_resp.headers["location"] == "/ui/console"
    assert ui_client.cookies.get("uav_ui_session")

    console_resp = ui_client.get("/ui/console")
    assert console_resp.status_code == 200
    assert "SaaS Console" in console_resp.text
    assert "Navigation" in console_resp.text

    logout_csrf = ui_client.cookies.get("uav_ui_csrf")
    assert logout_csrf
    logout_resp = ui_client.post(
        "/ui/logout",
        data={"csrf_token": logout_csrf},
        follow_redirects=False,
    )
    assert logout_resp.status_code == 303
    assert logout_resp.headers["location"] == "/ui/login"

    guarded_resp = ui_client.get("/ui/console", follow_redirects=False)
    assert guarded_resp.status_code == 303
    assert guarded_resp.headers["location"].startswith("/ui/login?next=")


def test_ui_legacy_query_token_still_supported(ui_client: TestClient) -> None:
    tenant_id = _create_tenant(ui_client, "ui-legacy-token-tenant")
    _bootstrap_admin(ui_client, tenant_id, "legacy_admin", "legacy-pass")
    token = _login_token(ui_client, tenant_id, "legacy_admin", "legacy-pass")

    page_resp = ui_client.get(f"/ui/command-center?token={token}")
    assert page_resp.status_code == 200
    assert "Layer Switch" in page_resp.text
    assert ui_client.cookies.get("uav_ui_session")

    cookie_only_resp = ui_client.get("/ui/command-center")
    assert cookie_only_resp.status_code == 200
    assert "Track Replay" in cookie_only_resp.text


def test_ui_rbac_menu_visibility_and_route_guard(ui_client: TestClient) -> None:
    tenant_id = _create_tenant(ui_client, "ui-rbac-tenant")
    _bootstrap_admin(ui_client, tenant_id, "rbac_admin", "rbac-pass")
    admin_token = _login_token(ui_client, tenant_id, "rbac_admin", "rbac-pass")

    role_resp = ui_client.post(
        "/api/identity/roles",
        json={"name": "inspection_only", "description": "inspection only role"},
        headers=_auth_header(admin_token),
    )
    assert role_resp.status_code == 201
    role_id = role_resp.json()["id"]

    perms_resp = ui_client.get("/api/identity/permissions", headers=_auth_header(admin_token))
    assert perms_resp.status_code == 200
    permission_rows = perms_resp.json()
    inspection_perm = next(item for item in permission_rows if item["name"] == "inspection:read")

    bind_perm_resp = ui_client.post(
        f"/api/identity/roles/{role_id}/permissions/{inspection_perm['id']}",
        headers=_auth_header(admin_token),
    )
    assert bind_perm_resp.status_code == 204

    create_user_resp = ui_client.post(
        "/api/identity/users",
        json={"username": "inspector", "password": "inspect-pass", "is_active": True},
        headers=_auth_header(admin_token),
    )
    assert create_user_resp.status_code == 201
    user_id = create_user_resp.json()["id"]

    bind_user_role_resp = ui_client.post(
        f"/api/identity/users/{user_id}/roles/{role_id}",
        headers=_auth_header(admin_token),
    )
    assert bind_user_role_resp.status_code == 204

    limited_token = _login_token(ui_client, tenant_id, "inspector", "inspect-pass")

    console_resp = ui_client.get(f"/ui/console?token={limited_token}")
    assert console_resp.status_code == 200
    assert "Inspection" in console_resp.text
    assert 'href="/ui/defects"' not in console_resp.text
    assert 'href="/ui/command-center"' not in console_resp.text

    defects_resp = ui_client.get(f"/ui/defects?token={limited_token}")
    assert defects_resp.status_code == 403

    inspection_resp = ui_client.get(f"/ui/inspection?token={limited_token}")
    assert inspection_resp.status_code == 200


def test_ui_login_rejects_invalid_csrf(ui_client: TestClient) -> None:
    tenant_id = _create_tenant(ui_client, "ui-csrf-tenant")
    _bootstrap_admin(ui_client, tenant_id, "csrf_admin", "csrf-pass")

    page_resp = ui_client.get("/ui/login")
    assert page_resp.status_code == 200

    login_resp = ui_client.post(
        "/ui/login",
        data={
            "tenant_id": tenant_id,
            "username": "csrf_admin",
            "password": "csrf-pass",
            "csrf_token": "invalid-token",
            "next": "/ui/console",
        },
    )
    assert login_resp.status_code == 400
    assert "invalid csrf token" in login_resp.text
