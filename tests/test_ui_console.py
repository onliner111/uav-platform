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
    PERM_OBSERVABILITY_READ,
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
    assert "角色化工作台" in console_resp.text
    assert "主导航" in console_resp.text

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
    assert "一张图值守模式" in page_resp.text
    assert "当前模式摘要" in page_resp.text
    assert "图层开关" in page_resp.text
    assert "事件时间轴" in page_resp.text
    assert ui_client.cookies.get("uav_ui_session")

    cookie_only_resp = ui_client.get("/ui/command-center")
    assert cookie_only_resp.status_code == 200
    assert "轨迹回放" in cookie_only_resp.text
    assert "当前焦点对象" in cookie_only_resp.text


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
    assert "巡检任务" in console_resp.text
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
    assert "任务队列" in readonly_page.text
    assert "主处理动作" not in readonly_page.text
    assert 'id="task-transition-btn"' not in readonly_page.text

    admin_page = ui_client.get(f"/ui/task-center?token={admin_token}")
    assert admin_page.status_code == 200
    assert "主处理动作" in admin_page.text
    assert 'id="task-transition-btn"' in admin_page.text


def test_ui_console_phase26_navigation_accessibility_markers(ui_client: TestClient) -> None:
    tenant_id = _create_tenant(ui_client, "ui-phase26-console-tenant")
    _bootstrap_admin(ui_client, tenant_id, "phase26_admin", "phase26-pass")
    token = _login_token(ui_client, tenant_id, "phase26_admin", "phase26-pass")

    response = ui_client.get(f"/ui/console?token={token}")
    assert response.status_code == 200
    assert "角色工作台" in response.text
    assert "总览" in response.text
    assert "态势" in response.text
    assert "执行" in response.text
    assert "治理" in response.text
    assert "平台" in response.text
    assert 'href="#console-main"' in response.text
    assert 'aria-label="Primary navigation"' in response.text
    assert "/static/ui_action_helpers.js" in response.text


def test_ui_console_role_workbench_visibility_is_permission_scoped(ui_client: TestClient) -> None:
    tenant_id = _create_tenant(ui_client, "ui-role-workbench-tenant")
    _bootstrap_admin(ui_client, tenant_id, "role_admin", "role-pass")
    admin_token = _login_token(ui_client, tenant_id, "role_admin", "role-pass")

    role_resp = ui_client.post(
        "/api/identity/roles",
        json={"name": "inspection_only_role_hub", "description": "inspection role hub"},
        headers=_auth_header(admin_token),
    )
    assert role_resp.status_code == 201
    role_id = role_resp.json()["id"]

    perms_resp = ui_client.get("/api/identity/permissions", headers=_auth_header(admin_token))
    assert perms_resp.status_code == 200
    permission_rows = perms_resp.json()
    inspection_perm = next(item for item in permission_rows if item["name"] == PERM_INSPECTION_READ)

    bind_perm_resp = ui_client.post(
        f"/api/identity/roles/{role_id}/permissions/{inspection_perm['id']}",
        headers=_auth_header(admin_token),
    )
    assert bind_perm_resp.status_code == 204

    create_user_resp = ui_client.post(
        "/api/identity/users",
        json={"username": "role_operator", "password": "role-pass-1", "is_active": True},
        headers=_auth_header(admin_token),
    )
    assert create_user_resp.status_code == 201
    user_id = create_user_resp.json()["id"]

    bind_user_role_resp = ui_client.post(
        f"/api/identity/users/{user_id}/roles/{role_id}",
        headers=_auth_header(admin_token),
    )
    assert bind_user_role_resp.status_code == 204

    limited_token = _login_token(ui_client, tenant_id, "role_operator", "role-pass-1")

    console_resp = ui_client.get(f"/ui/console?token={limited_token}")
    assert console_resp.status_code == 200
    assert "现场执行工作台" in console_resp.text
    assert "指挥工作台" not in console_resp.text

    operator_resp = ui_client.get(f"/ui/workbench/operator?token={limited_token}")
    assert operator_resp.status_code == 200
    assert "现场执行工作台" in operator_resp.text
    assert 'href="/ui/inspection"' in operator_resp.text

    forbidden_resp = ui_client.get(f"/ui/workbench/commander?token={limited_token}")
    assert forbidden_resp.status_code == 403


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
    assert "缺陷列表" in defects_page.text
    assert "defect.write" in defects_page.text
    assert 'id="assign-btn" disabled' in defects_page.text
    assert 'id="status-btn"' in defects_page.text

    emergency_page = ui_client.get(f"/ui/emergency?token={readonly_token}")
    assert emergency_page.status_code == 200
    assert "近期事件" in emergency_page.text
    assert "1. 地图选点" in emergency_page.text
    assert "当前账号缺少" in emergency_page.text
    assert 'id="create-incident-btn"' not in emergency_page.text
    assert 'id="create-task-btn"' not in emergency_page.text

    admin_emergency_page = ui_client.get(f"/ui/emergency?token={admin_token}")
    assert admin_emergency_page.status_code == 200
    assert "确定事件位置" in admin_emergency_page.text
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
    assert "值守 SLA 概览" in readonly_alerts_page.text
    assert "告警类型" in readonly_alerts_page.text
    assert "Alert Type" not in readonly_alerts_page.text
    assert 'id="alert-ack-btn" type="button" style="margin-top:10px;" disabled' in readonly_alerts_page.text
    assert 'id="routing-create-btn" type="button" style="margin-top:10px;" disabled' in readonly_alerts_page.text

    readonly_compliance_page = ui_client.get(f"/ui/compliance?token={readonly_token}")
    assert readonly_compliance_page.status_code == 200
    assert "审批与流程处理" in readonly_compliance_page.text
    assert "审批流可视化" in readonly_compliance_page.text
    assert "管理员高级配置" not in readonly_compliance_page.text
    assert 'id="approval-create-btn" type="button" class="stack-gap-sm" disabled' in readonly_compliance_page.text
    assert 'id="zone-create-btn" type="button" class="stack-gap-sm" disabled' in readonly_compliance_page.text

    admin_alerts_page = ui_client.get(f"/ui/alerts?token={admin_token}")
    assert admin_alerts_page.status_code == 200
    assert 'id="alert-ack-btn" type="button" style="margin-top:10px;" disabled' not in admin_alerts_page.text

    admin_compliance_page = ui_client.get(f"/ui/compliance?token={admin_token}")
    assert admin_compliance_page.status_code == 200
    assert "管理员高级配置" in admin_compliance_page.text
    assert "流程步骤配置\uFF08高级\uFF09" in admin_compliance_page.text
    assert "流程步骤 JSON" not in admin_compliance_page.text
    assert 'id="approval-create-btn" type="button" style="margin-top:10px;" disabled' not in admin_compliance_page.text


def test_ui_phase32_assets_compliance_emergency_use_object_selection_patterns(ui_client: TestClient) -> None:
    tenant_id = _create_tenant(ui_client, "ui-phase32-productized-tenant")
    _bootstrap_admin(ui_client, tenant_id, "phase32_admin", "phase32-pass")
    admin_token = _login_token(ui_client, tenant_id, "phase32_admin", "phase32-pass")

    inspection_page = ui_client.get(f"/ui/inspection?token={admin_token}")
    assert inspection_page.status_code == 200
    assert "巡检任务创建向导" in inspection_page.text
    assert "1. 选择模板" in inspection_page.text
    assert "确认并创建" in inspection_page.text
    assert "推荐提示" in inspection_page.text

    assets_page = ui_client.get(f"/ui/assets?token={admin_token}")
    assert assets_page.status_code == 200
    assert "资产处理工作区" in assets_page.text
    assert "当前资产" in assets_page.text
    assert "无需手动填写资产 ID" in assets_page.text
    assert "新建维护工单" in assets_page.text

    compliance_page = ui_client.get(f"/ui/compliance?token={admin_token}")
    assert compliance_page.status_code == 200
    assert "审批待办" in compliance_page.text
    assert "审批流可视化" in compliance_page.text
    assert "审批与流程处理" in compliance_page.text
    assert "高级配置" in compliance_page.text
    assert "当前模板" in compliance_page.text

    emergency_page = ui_client.get(f"/ui/emergency?token={admin_token}")
    assert emergency_page.status_code == 200
    assert "应急事件处置" in emergency_page.text
    assert "联动任务" in emergency_page.text
    assert "风险提示" in emergency_page.text
    assert "当前坐标" in emergency_page.text
    assert "为当前事件一键建任务" in emergency_page.text
    assert "当前事件" in emergency_page.text


def test_ui_phase35_mobile_field_pages_present_mobile_first_copy(ui_client: TestClient) -> None:
    tenant_id = _create_tenant(ui_client, "ui-phase35-mobile-tenant")
    _bootstrap_admin(ui_client, tenant_id, "phase35_admin", "phase35-pass")
    admin_token = _login_token(ui_client, tenant_id, "phase35_admin", "phase35-pass")

    create_template_resp = ui_client.post(
        "/api/inspection/templates",
        json={
            "name": "phase35-template",
            "category": "field-mobile",
            "description": "phase35 mobile template",
            "is_active": True,
        },
        headers=_auth_header(admin_token),
    )
    assert create_template_resp.status_code == 201
    template_id = create_template_resp.json()["id"]

    create_task_resp = ui_client.post(
        "/api/inspection/tasks",
        json={
            "name": "phase35-task",
            "template_id": template_id,
            "mission_id": None,
            "area_geom": "",
            "priority": 5,
        },
        headers=_auth_header(admin_token),
    )
    assert create_task_resp.status_code == 201
    task_id = create_task_resp.json()["id"]

    task_detail_page = ui_client.get(f"/ui/inspection/tasks/{task_id}?token={admin_token}")
    assert task_detail_page.status_code == 200
    assert "现场执行工作台" in task_detail_page.text
    assert "网络状态" in task_detail_page.text
    assert "重试上一笔" in task_detail_page.text
    assert "现场备注与媒体预留" in task_detail_page.text

    defects_page = ui_client.get(f"/ui/defects?token={admin_token}")
    assert defects_page.status_code == 200
    assert "移动端缺陷工作区" in defects_page.text
    assert "重试上一笔分派" in defects_page.text
    assert "重试上一笔状态更新" in defects_page.text
    assert "现场补充说明" in defects_page.text


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
    assert "成果数据工作区" in readonly_reports_page.text
    assert 'id="outcome-create-btn" type="button" style="margin-top:10px;" disabled' in readonly_reports_page.text
    assert 'id="report-template-create-btn" type="button" style="margin-top:10px;" disabled' in readonly_reports_page.text

    readonly_ai_page = ui_client.get(f"/ui/ai-governance?token={readonly_token}")
    assert readonly_ai_page.status_code == 200
    assert "模型目录与版本治理" in readonly_ai_page.text
    assert 'id="ai-model-create-btn" type="button" class="stack-gap-sm" disabled' in readonly_ai_page.text
    assert 'id="ai-version-create-btn" type="button" class="stack-gap-sm" disabled' in readonly_ai_page.text

    admin_reports_page = ui_client.get(f"/ui/reports?token={admin_token}")
    assert admin_reports_page.status_code == 200
    assert "补充说明\uFF08高级配置\uFF09" in admin_reports_page.text
    assert "载荷 JSON" not in admin_reports_page.text
    assert 'id="outcome-create-btn" type="button" style="margin-top:10px;" disabled' not in admin_reports_page.text
    assert 'id="report-template-create-btn" type="button" style="margin-top:10px;" disabled' not in admin_reports_page.text

    admin_ai_page = ui_client.get(f"/ui/ai-governance?token={admin_token}")
    assert admin_ai_page.status_code == 200
    assert 'id="ai-model-create-btn" type="button" class="stack-gap-sm" disabled' not in admin_ai_page.text
    assert 'id="ai-version-create-btn" type="button" class="stack-gap-sm" disabled' not in admin_ai_page.text


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
    assert "计费与配额操作" in readonly_commercial_page.text
    assert (
        'id="billing-plan-create-btn" type="button" class="stack-gap-sm" disabled'
        in readonly_commercial_page.text
    )

    readonly_open_platform_page = ui_client.get(f"/ui/open-platform?token={readonly_token}")
    assert readonly_open_platform_page.status_code == 200
    assert "开放平台访问与 Webhook 管理" in readonly_open_platform_page.text
    assert (
        'id="open-credential-create-btn" type="button" class="stack-gap-sm" disabled'
        in readonly_open_platform_page.text
    )
    assert (
        'id="open-webhook-create-btn" type="button" class="stack-gap-sm" disabled'
        in readonly_open_platform_page.text
    )

    admin_commercial_page = ui_client.get(f"/ui/commercial-ops?token={admin_token}")
    assert admin_commercial_page.status_code == 200
    assert (
        'id="billing-plan-create-btn" type="button" class="stack-gap-sm" disabled'
        not in admin_commercial_page.text
    )

    admin_open_platform_page = ui_client.get(f"/ui/open-platform?token={admin_token}")
    assert admin_open_platform_page.status_code == 200
    assert (
        'id="open-credential-create-btn" type="button" class="stack-gap-sm" disabled'
        not in admin_open_platform_page.text
    )
    assert (
        'id="open-webhook-create-btn" type="button" class="stack-gap-sm" disabled'
        not in admin_open_platform_page.text
    )


def test_ui_phase31_observability_reliability_write_visibility(ui_client: TestClient) -> None:
    tenant_id = _create_tenant(ui_client, "ui-phase31-readonly-tenant")
    _bootstrap_admin(ui_client, tenant_id, "phase31_admin", "phase31-pass")
    admin_token = _login_token(ui_client, tenant_id, "phase31_admin", "phase31-pass")

    role_resp = ui_client.post(
        "/api/identity/roles",
        json={"name": "phase31_readonly", "description": "observability read only"},
        headers=_auth_header(admin_token),
    )
    assert role_resp.status_code == 201
    role_id = role_resp.json()["id"]

    perms_resp = ui_client.get("/api/identity/permissions", headers=_auth_header(admin_token))
    assert perms_resp.status_code == 200
    permission_rows = perms_resp.json()
    observability_read_perm = next(item for item in permission_rows if item["name"] == PERM_OBSERVABILITY_READ)

    bind_perm_resp = ui_client.post(
        f"/api/identity/roles/{role_id}/permissions/{observability_read_perm['id']}",
        headers=_auth_header(admin_token),
    )
    assert bind_perm_resp.status_code == 204

    create_user_resp = ui_client.post(
        "/api/identity/users",
        json={"username": "phase31_reader", "password": "phase31-reader-pass", "is_active": True},
        headers=_auth_header(admin_token),
    )
    assert create_user_resp.status_code == 201
    user_id = create_user_resp.json()["id"]

    bind_user_role_resp = ui_client.post(
        f"/api/identity/users/{user_id}/roles/{role_id}",
        headers=_auth_header(admin_token),
    )
    assert bind_user_role_resp.status_code == 204

    readonly_token = _login_token(ui_client, tenant_id, "phase31_reader", "phase31-reader-pass")

    readonly_observability_page = ui_client.get(f"/ui/observability?token={readonly_token}")
    assert readonly_observability_page.status_code == 200
    assert "可观测与 SLO 值守" in readonly_observability_page.text
    assert 'id="obv-signal-ingest-btn" type="button" class="stack-gap-sm" disabled' in readonly_observability_page.text
    assert 'id="obv-slo-create-btn" type="button" class="stack-gap-sm" disabled' in readonly_observability_page.text

    readonly_reliability_page = ui_client.get(f"/ui/reliability?token={readonly_token}")
    assert readonly_reliability_page.status_code == 200
    assert "可靠性运行手册" in readonly_reliability_page.text
    assert 'id="rel-backup-run-btn" type="button" class="stack-gap-sm" disabled' in readonly_reliability_page.text
    assert 'id="rel-capacity-upsert-btn" type="button" class="stack-gap-sm" disabled' in readonly_reliability_page.text

    admin_observability_page = ui_client.get(f"/ui/observability?token={admin_token}")
    assert admin_observability_page.status_code == 200
    assert (
        'id="obv-signal-ingest-btn" type="button" class="stack-gap-sm" disabled'
        not in admin_observability_page.text
    )

    admin_reliability_page = ui_client.get(f"/ui/reliability?token={admin_token}")
    assert admin_reliability_page.status_code == 200
    assert 'id="rel-backup-run-btn" type="button" class="stack-gap-sm" disabled' not in admin_reliability_page.text


def test_ui_console_hides_internal_only_pages_from_primary_navigation(ui_client: TestClient) -> None:
    tenant_id = _create_tenant(ui_client, "ui-primary-nav-tenant")
    _bootstrap_admin(ui_client, tenant_id, "primary_nav_admin", "primary-nav-pass")
    token = _login_token(ui_client, tenant_id, "primary_nav_admin", "primary-nav-pass")

    response = ui_client.get(f"/ui/console?token={token}")
    assert response.status_code == 200
    assert "管理员专项" in response.text
    assert "管理员专项入口" in response.text
    assert 'href="/ui/observability"' in response.text
    assert 'href="/ui/reliability"' in response.text
    assert 'href="/ui/ai-governance"' in response.text
    assert 'href="/ui/commercial-ops"' in response.text
    assert 'href="/ui/open-platform"' in response.text
    assert '<a href="/ui/observability" data-nav-link>可观测性</a>' in response.text
    assert '<span class="status-pill muted">专项</span>' in response.text
    assert 'href="/ui/platform"' in response.text
    assert 'href="/ui/reports"' in response.text


def test_ui_action_helpers_runtime_messages_are_localized(ui_client: TestClient) -> None:
    response = ui_client.get("/static/ui_action_helpers.js")
    assert response.status_code == 200
    assert "处理中..." in response.text
    assert "请求失败\uFF0C请稍后重试。" in response.text
    assert "Processing..." not in response.text
    assert "request failed" not in response.text


def test_ui_platform_rbac_matrix_rendering(ui_client: TestClient) -> None:
    tenant_id = _create_tenant(ui_client, "ui-phase26-platform-tenant")
    _bootstrap_admin(ui_client, tenant_id, "platform_admin", "platform-pass")
    token = _login_token(ui_client, tenant_id, "platform_admin", "platform-pass")

    response = ui_client.get(f"/ui/platform?token={token}")
    assert response.status_code == 200
    assert "RBAC 可见性矩阵" in response.text
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
