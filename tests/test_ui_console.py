from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlmodel import SQLModel, create_engine

from app import main as app_main
from app.domain.permissions import (
    PERM_AI_READ,
    PERM_ALERT_READ,
    PERM_APPROVAL_READ,
    PERM_BILLING_READ,
    PERM_DEFECT_READ,
    PERM_INCIDENT_READ,
    PERM_INSPECTION_READ,
    PERM_MISSION_READ,
    PERM_REPORTING_READ,
)
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


def test_ui_task_center_action_visibility_by_write_permission(ui_client: TestClient) -> None:
    tenant_id = _create_tenant(ui_client, "ui-task-center-rbac-tenant")
    _bootstrap_admin(ui_client, tenant_id, "task_admin", "task-pass")
    admin_token = _login_token(ui_client, tenant_id, "task_admin", "task-pass")

    role_resp = ui_client.post(
        "/api/identity/roles",
        json={"name": "task_readonly", "description": "mission read only"},
        headers=_auth_header(admin_token),
    )
    assert role_resp.status_code == 201
    role_id = role_resp.json()["id"]

    perms_resp = ui_client.get("/api/identity/permissions", headers=_auth_header(admin_token))
    assert perms_resp.status_code == 200
    permission_rows = perms_resp.json()
    mission_read_perm = next(item for item in permission_rows if item["name"] == "mission.read")

    bind_perm_resp = ui_client.post(
        f"/api/identity/roles/{role_id}/permissions/{mission_read_perm['id']}",
        headers=_auth_header(admin_token),
    )
    assert bind_perm_resp.status_code == 204

    create_user_resp = ui_client.post(
        "/api/identity/users",
        json={"username": "task_reader", "password": "task-reader-pass", "is_active": True},
        headers=_auth_header(admin_token),
    )
    assert create_user_resp.status_code == 201
    user_id = create_user_resp.json()["id"]

    bind_user_role_resp = ui_client.post(
        f"/api/identity/users/{user_id}/roles/{role_id}",
        headers=_auth_header(admin_token),
    )
    assert bind_user_role_resp.status_code == 204

    readonly_token = _login_token(ui_client, tenant_id, "task_reader", "task-reader-pass")

    readonly_page = ui_client.get(f"/ui/task-center?token={readonly_token}")
    assert readonly_page.status_code == 200
    assert "Task Queue" in readonly_page.text
    assert "Quick Actions" not in readonly_page.text
    assert 'id="task-transition-btn"' not in readonly_page.text

    admin_page = ui_client.get(f"/ui/task-center?token={admin_token}")
    assert admin_page.status_code == 200
    assert "Quick Actions" in admin_page.text
    assert 'id="task-transition-btn"' in admin_page.text


def test_ui_console_phase26_navigation_accessibility_markers(ui_client: TestClient) -> None:
    tenant_id = _create_tenant(ui_client, "ui-phase26-console-tenant")
    _bootstrap_admin(ui_client, tenant_id, "phase26_admin", "phase26-pass")
    token = _login_token(ui_client, tenant_id, "phase26_admin", "phase26-pass")

    response = ui_client.get(f"/ui/console?token={token}")
    assert response.status_code == 200
    assert "Overview" in response.text
    assert "Observe" in response.text
    assert "Execute" in response.text
    assert "Govern" in response.text
    assert "Platform" in response.text
    assert 'href="#console-main"' in response.text
    assert 'aria-label="Primary navigation"' in response.text
    assert "/static/ui_action_helpers.js" in response.text


def test_ui_execute_pages_readonly_mode_hides_write_actions(ui_client: TestClient) -> None:
    tenant_id = _create_tenant(ui_client, "ui-phase27-readonly-tenant")
    _bootstrap_admin(ui_client, tenant_id, "phase27_admin", "phase27-pass")
    admin_token = _login_token(ui_client, tenant_id, "phase27_admin", "phase27-pass")

    role_resp = ui_client.post(
        "/api/identity/roles",
        json={"name": "execute_readonly", "description": "defect+incident read only"},
        headers=_auth_header(admin_token),
    )
    assert role_resp.status_code == 201
    role_id = role_resp.json()["id"]

    perms_resp = ui_client.get("/api/identity/permissions", headers=_auth_header(admin_token))
    assert perms_resp.status_code == 200
    permission_rows = perms_resp.json()
    defect_read_perm = next(item for item in permission_rows if item["name"] == PERM_DEFECT_READ)
    incident_read_perm = next(item for item in permission_rows if item["name"] == PERM_INCIDENT_READ)

    bind_defect_perm_resp = ui_client.post(
        f"/api/identity/roles/{role_id}/permissions/{defect_read_perm['id']}",
        headers=_auth_header(admin_token),
    )
    assert bind_defect_perm_resp.status_code == 204
    bind_incident_perm_resp = ui_client.post(
        f"/api/identity/roles/{role_id}/permissions/{incident_read_perm['id']}",
        headers=_auth_header(admin_token),
    )
    assert bind_incident_perm_resp.status_code == 204

    create_user_resp = ui_client.post(
        "/api/identity/users",
        json={"username": "execute_reader", "password": "execute-reader-pass", "is_active": True},
        headers=_auth_header(admin_token),
    )
    assert create_user_resp.status_code == 201
    user_id = create_user_resp.json()["id"]

    bind_user_role_resp = ui_client.post(
        f"/api/identity/users/{user_id}/roles/{role_id}",
        headers=_auth_header(admin_token),
    )
    assert bind_user_role_resp.status_code == 204

    readonly_token = _login_token(ui_client, tenant_id, "execute_reader", "execute-reader-pass")

    defects_page = ui_client.get(f"/ui/defects?token={readonly_token}")
    assert defects_page.status_code == 200
    assert "Defect List" in defects_page.text
    assert "`defect.write` permission is required for assign/status actions." in defects_page.text
    assert 'id="assign-btn" disabled' in defects_page.text
    assert 'id="status-btn"' in defects_page.text

    emergency_page = ui_client.get(f"/ui/emergency?token={readonly_token}")
    assert emergency_page.status_code == 200
    assert "Recent Incidents" in emergency_page.text
    assert "`incident.write` permission is required for create actions." in emergency_page.text
    assert 'id="create-incident-btn"' not in emergency_page.text
    assert 'id="create-task-btn"' not in emergency_page.text

    admin_emergency_page = ui_client.get(f"/ui/emergency?token={admin_token}")
    assert admin_emergency_page.status_code == 200
    assert 'id="create-incident-btn"' in admin_emergency_page.text
    assert 'id="create-task-btn"' in admin_emergency_page.text


def test_ui_phase28_compliance_alert_workbench_write_visibility(ui_client: TestClient) -> None:
    tenant_id = _create_tenant(ui_client, "ui-phase28-readonly-tenant")
    _bootstrap_admin(ui_client, tenant_id, "phase28_admin", "phase28-pass")
    admin_token = _login_token(ui_client, tenant_id, "phase28_admin", "phase28-pass")

    role_resp = ui_client.post(
        "/api/identity/roles",
        json={"name": "phase28_readonly", "description": "alert/compliance read only"},
        headers=_auth_header(admin_token),
    )
    assert role_resp.status_code == 201
    role_id = role_resp.json()["id"]

    perms_resp = ui_client.get("/api/identity/permissions", headers=_auth_header(admin_token))
    assert perms_resp.status_code == 200
    permission_rows = perms_resp.json()
    alert_read_perm = next(item for item in permission_rows if item["name"] == PERM_ALERT_READ)
    approval_read_perm = next(item for item in permission_rows if item["name"] == PERM_APPROVAL_READ)
    mission_read_perm = next(item for item in permission_rows if item["name"] == PERM_MISSION_READ)

    for perm_id in (alert_read_perm["id"], approval_read_perm["id"], mission_read_perm["id"]):
        bind_perm_resp = ui_client.post(
            f"/api/identity/roles/{role_id}/permissions/{perm_id}",
            headers=_auth_header(admin_token),
        )
        assert bind_perm_resp.status_code == 204

    create_user_resp = ui_client.post(
        "/api/identity/users",
        json={"username": "phase28_reader", "password": "phase28-reader-pass", "is_active": True},
        headers=_auth_header(admin_token),
    )
    assert create_user_resp.status_code == 201
    user_id = create_user_resp.json()["id"]

    bind_user_role_resp = ui_client.post(
        f"/api/identity/users/{user_id}/roles/{role_id}",
        headers=_auth_header(admin_token),
    )
    assert bind_user_role_resp.status_code == 204

    readonly_token = _login_token(ui_client, tenant_id, "phase28_reader", "phase28-reader-pass")

    readonly_alerts_page = ui_client.get(f"/ui/alerts?token={readonly_token}")
    assert readonly_alerts_page.status_code == 200
    assert "SLA Overview" in readonly_alerts_page.text
    assert 'id="alert-ack-btn" type="button" style="margin-top:10px;" disabled' in readonly_alerts_page.text
    assert 'id="routing-create-btn" type="button" style="margin-top:10px;" disabled' in readonly_alerts_page.text

    readonly_compliance_page = ui_client.get(f"/ui/compliance?token={readonly_token}")
    assert readonly_compliance_page.status_code == 200
    assert "Approval Flow Workbench" in readonly_compliance_page.text
    assert 'id="approval-create-btn" type="button" style="margin-top:10px;" disabled' in readonly_compliance_page.text
    assert 'id="zone-create-btn" type="button" style="margin-top:10px;" disabled' in readonly_compliance_page.text

    admin_alerts_page = ui_client.get(f"/ui/alerts?token={admin_token}")
    assert admin_alerts_page.status_code == 200
    assert 'id="alert-ack-btn" type="button" style="margin-top:10px;" disabled' not in admin_alerts_page.text

    admin_compliance_page = ui_client.get(f"/ui/compliance?token={admin_token}")
    assert admin_compliance_page.status_code == 200
    assert 'id="approval-create-btn" type="button" style="margin-top:10px;" disabled' not in admin_compliance_page.text


def test_ui_phase29_data_ai_workbench_write_visibility(ui_client: TestClient) -> None:
    tenant_id = _create_tenant(ui_client, "ui-phase29-readonly-tenant")
    _bootstrap_admin(ui_client, tenant_id, "phase29_admin", "phase29-pass")
    admin_token = _login_token(ui_client, tenant_id, "phase29_admin", "phase29-pass")

    role_resp = ui_client.post(
        "/api/identity/roles",
        json={"name": "phase29_readonly", "description": "data and ai read only"},
        headers=_auth_header(admin_token),
    )
    assert role_resp.status_code == 201
    role_id = role_resp.json()["id"]

    perms_resp = ui_client.get("/api/identity/permissions", headers=_auth_header(admin_token))
    assert perms_resp.status_code == 200
    permission_rows = perms_resp.json()
    reporting_read_perm = next(item for item in permission_rows if item["name"] == PERM_REPORTING_READ)
    inspection_read_perm = next(item for item in permission_rows if item["name"] == PERM_INSPECTION_READ)
    ai_read_perm = next(item for item in permission_rows if item["name"] == PERM_AI_READ)

    for perm_id in (reporting_read_perm["id"], inspection_read_perm["id"], ai_read_perm["id"]):
        bind_perm_resp = ui_client.post(
            f"/api/identity/roles/{role_id}/permissions/{perm_id}",
            headers=_auth_header(admin_token),
        )
        assert bind_perm_resp.status_code == 204

    create_user_resp = ui_client.post(
        "/api/identity/users",
        json={"username": "phase29_reader", "password": "phase29-reader-pass", "is_active": True},
        headers=_auth_header(admin_token),
    )
    assert create_user_resp.status_code == 201
    user_id = create_user_resp.json()["id"]

    bind_user_role_resp = ui_client.post(
        f"/api/identity/users/{user_id}/roles/{role_id}",
        headers=_auth_header(admin_token),
    )
    assert bind_user_role_resp.status_code == 204

    readonly_token = _login_token(ui_client, tenant_id, "phase29_reader", "phase29-reader-pass")

    readonly_reports_page = ui_client.get(f"/ui/reports?token={readonly_token}")
    assert readonly_reports_page.status_code == 200
    assert "Data Outcomes Workbench" in readonly_reports_page.text
    assert 'id="outcome-create-btn" type="button" style="margin-top:10px;" disabled' in readonly_reports_page.text
    assert 'id="report-template-create-btn" type="button" style="margin-top:10px;" disabled' in readonly_reports_page.text

    readonly_ai_page = ui_client.get(f"/ui/ai-governance?token={readonly_token}")
    assert readonly_ai_page.status_code == 200
    assert "Model Catalog + Version Governance" in readonly_ai_page.text
    assert 'id="ai-model-create-btn" type="button" style="margin-top:10px;" disabled' in readonly_ai_page.text
    assert 'id="ai-version-create-btn" type="button" style="margin-top:10px;" disabled' in readonly_ai_page.text

    admin_reports_page = ui_client.get(f"/ui/reports?token={admin_token}")
    assert admin_reports_page.status_code == 200
    assert 'id="outcome-create-btn" type="button" style="margin-top:10px;" disabled' not in admin_reports_page.text
    assert 'id="report-template-create-btn" type="button" style="margin-top:10px;" disabled' not in admin_reports_page.text

    admin_ai_page = ui_client.get(f"/ui/ai-governance?token={admin_token}")
    assert admin_ai_page.status_code == 200
    assert 'id="ai-model-create-btn" type="button" style="margin-top:10px;" disabled' not in admin_ai_page.text
    assert 'id="ai-version-create-btn" type="button" style="margin-top:10px;" disabled' not in admin_ai_page.text


def test_ui_phase30_commercial_open_platform_write_visibility(ui_client: TestClient) -> None:
    tenant_id = _create_tenant(ui_client, "ui-phase30-readonly-tenant")
    _bootstrap_admin(ui_client, tenant_id, "phase30_admin", "phase30-pass")
    admin_token = _login_token(ui_client, tenant_id, "phase30_admin", "phase30-pass")

    role_resp = ui_client.post(
        "/api/identity/roles",
        json={"name": "phase30_readonly", "description": "commercial and open platform read only"},
        headers=_auth_header(admin_token),
    )
    assert role_resp.status_code == 201
    role_id = role_resp.json()["id"]

    perms_resp = ui_client.get("/api/identity/permissions", headers=_auth_header(admin_token))
    assert perms_resp.status_code == 200
    permission_rows = perms_resp.json()
    billing_read_perm = next(item for item in permission_rows if item["name"] == PERM_BILLING_READ)
    reporting_read_perm = next(item for item in permission_rows if item["name"] == PERM_REPORTING_READ)

    for perm_id in (billing_read_perm["id"], reporting_read_perm["id"]):
        bind_perm_resp = ui_client.post(
            f"/api/identity/roles/{role_id}/permissions/{perm_id}",
            headers=_auth_header(admin_token),
        )
        assert bind_perm_resp.status_code == 204

    create_user_resp = ui_client.post(
        "/api/identity/users",
        json={"username": "phase30_reader", "password": "phase30-reader-pass", "is_active": True},
        headers=_auth_header(admin_token),
    )
    assert create_user_resp.status_code == 201
    user_id = create_user_resp.json()["id"]

    bind_user_role_resp = ui_client.post(
        f"/api/identity/users/{user_id}/roles/{role_id}",
        headers=_auth_header(admin_token),
    )
    assert bind_user_role_resp.status_code == 204

    readonly_token = _login_token(ui_client, tenant_id, "phase30_reader", "phase30-reader-pass")

    readonly_commercial_page = ui_client.get(f"/ui/commercial-ops?token={readonly_token}")
    assert readonly_commercial_page.status_code == 200
    assert "Billing + Quota Operations" in readonly_commercial_page.text
    assert (
        'id="billing-plan-create-btn" type="button" style="margin-top:10px;" disabled'
        in readonly_commercial_page.text
    )

    readonly_open_platform_page = ui_client.get(f"/ui/open-platform?token={readonly_token}")
    assert readonly_open_platform_page.status_code == 200
    assert "Open Platform Access + Webhook Ops" in readonly_open_platform_page.text
    assert (
        'id="open-credential-create-btn" type="button" style="margin-top:10px;" disabled'
        in readonly_open_platform_page.text
    )
    assert (
        'id="open-webhook-create-btn" type="button" style="margin-top:10px;" disabled'
        in readonly_open_platform_page.text
    )

    admin_commercial_page = ui_client.get(f"/ui/commercial-ops?token={admin_token}")
    assert admin_commercial_page.status_code == 200
    assert (
        'id="billing-plan-create-btn" type="button" style="margin-top:10px;" disabled'
        not in admin_commercial_page.text
    )

    admin_open_platform_page = ui_client.get(f"/ui/open-platform?token={admin_token}")
    assert admin_open_platform_page.status_code == 200
    assert (
        'id="open-credential-create-btn" type="button" style="margin-top:10px;" disabled'
        not in admin_open_platform_page.text
    )
    assert (
        'id="open-webhook-create-btn" type="button" style="margin-top:10px;" disabled'
        not in admin_open_platform_page.text
    )


def test_ui_platform_rbac_matrix_rendering(ui_client: TestClient) -> None:
    tenant_id = _create_tenant(ui_client, "ui-phase26-platform-tenant")
    _bootstrap_admin(ui_client, tenant_id, "platform_admin", "platform-pass")
    token = _login_token(ui_client, tenant_id, "platform_admin", "platform-pass")

    response = ui_client.get(f"/ui/platform?token={token}")
    assert response.status_code == 200
    assert "RBAC UI Visibility Matrix" in response.text
    assert "/ui/task-center" in response.text
    assert "mission.read" in response.text
    assert "mission.write" in response.text


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
