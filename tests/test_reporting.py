from __future__ import annotations

from collections.abc import Generator
from datetime import timedelta
from pathlib import Path
from zipfile import ZipFile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine, select

from app import main as app_main
from app.domain.models import AuditLog, OutcomeReportExport, now_utc
from app.infra import audit, db, events


@pytest.fixture()
def reporting_client(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Generator[TestClient, None, None]:
    db_path = tmp_path / "reporting_test.db"
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


def _create_mission(client: TestClient, token: str, name: str) -> str:
    response = client.post(
        "/api/mission/missions",
        json={
            "name": name,
            "type": "POINT_TASK",
            "payload": {},
            "constraints": {},
        },
        headers=_auth_header(token),
    )
    assert response.status_code == 201
    return response.json()["id"]


def _create_template(client: TestClient, token: str, name: str) -> str:
    response = client.post(
        "/api/inspection/templates",
        json={"name": name, "category": "reporting", "description": "reporting", "is_active": True},
        headers=_auth_header(token),
    )
    assert response.status_code == 201
    return response.json()["id"]


def _create_task(client: TestClient, token: str, template_id: str, name: str, mission_id: str | None = None) -> str:
    response = client.post(
        "/api/inspection/tasks",
        json={
            "name": name,
            "template_id": template_id,
            "mission_id": mission_id,
            "area_geom": "POLYGON((114.30 30.58,114.31 30.58,114.31 30.59,114.30 30.59,114.30 30.58))",
            "priority": 3,
            "status": "SCHEDULED",
        },
        headers=_auth_header(token),
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_reporting_overview_is_tenant_scoped(reporting_client: TestClient) -> None:
    tenant_a = _create_tenant(reporting_client, "reporting-scope-a")
    tenant_b = _create_tenant(reporting_client, "reporting-scope-b")
    _bootstrap_admin(reporting_client, tenant_a, "admin_a", "pass-a")
    _bootstrap_admin(reporting_client, tenant_b, "admin_b", "pass-b")
    token_a = _login(reporting_client, tenant_a, "admin_a", "pass-a")
    token_b = _login(reporting_client, tenant_b, "admin_b", "pass-b")

    _create_mission(reporting_client, token_a, "mission-a-1")
    _create_mission(reporting_client, token_a, "mission-a-2")
    _create_mission(reporting_client, token_b, "mission-b-1")

    overview_a = reporting_client.get("/api/reporting/overview", headers=_auth_header(token_a))
    overview_b = reporting_client.get("/api/reporting/overview", headers=_auth_header(token_b))

    assert overview_a.status_code == 200
    assert overview_b.status_code == 200

    body_a = overview_a.json()
    body_b = overview_b.json()
    assert body_a["missions_total"] == 2
    assert body_b["missions_total"] == 1
    assert body_a["inspections_total"] == 0
    assert body_b["inspections_total"] == 0
    assert body_a["defects_total"] == 0
    assert body_b["defects_total"] == 0


def test_reporting_export_supports_task_time_topic_scope(reporting_client: TestClient) -> None:
    tenant_id = _create_tenant(reporting_client, "reporting-export-scope")
    _bootstrap_admin(reporting_client, tenant_id, "admin", "admin-pass")
    token = _login(reporting_client, tenant_id, "admin", "admin-pass")

    mission_id = _create_mission(reporting_client, token, "reporting-mission")
    template_id = _create_template(reporting_client, token, "reporting-template")
    task_id = _create_task(reporting_client, token, template_id, "reporting-task", mission_id=mission_id)

    obs_resp = reporting_client.post(
        f"/api/inspection/tasks/{task_id}/observations",
        json={
            "position_lat": 30.5801,
            "position_lon": 114.3001,
            "alt_m": 50.0,
            "item_code": "RPT-1",
            "severity": 2,
            "note": "reporting observation",
            "confidence": 0.9,
        },
        headers=_auth_header(token),
    )
    assert obs_resp.status_code == 201

    ingest_resp = reporting_client.post(
        "/api/telemetry/ingest",
        json={
            "tenant_id": "spoofed",
            "drone_id": "reporting-drone",
            "position": {"lat": 30.12, "lon": 114.45, "alt_m": 120.0},
            "battery": {"percent": 10.0},
            "link": {"latency_ms": 50},
            "mode": "AUTO",
            "health": {"low_battery": True},
        },
        headers=_auth_header(token),
    )
    assert ingest_resp.status_code == 200

    alerts_resp = reporting_client.get("/api/alert/alerts", headers=_auth_header(token))
    assert alerts_resp.status_code == 200
    alert_id = alerts_resp.json()[0]["id"]
    ack_resp = reporting_client.post(
        f"/api/alert/alerts/{alert_id}/ack",
        json={"comment": "for reporting export"},
        headers=_auth_header(token),
    )
    assert ack_resp.status_code == 200

    export_resp = reporting_client.post(
        "/api/reporting/export",
        json={"title": "Phase13 Report", "task_id": task_id, "topic": "other"},
        headers=_auth_header(token),
    )
    assert export_resp.status_code == 200
    export_path = Path(export_resp.json()["file_path"])
    assert export_path.exists()
    content = export_path.read_bytes()
    assert b"outcomes_total=" in content
    assert b"alerts_total=" in content
    assert b"alert_actions_total=" in content


def test_outcome_report_template_and_export_pdf_word(reporting_client: TestClient) -> None:
    tenant_a = _create_tenant(reporting_client, "reporting-outcome-template-a")
    tenant_b = _create_tenant(reporting_client, "reporting-outcome-template-b")
    _bootstrap_admin(reporting_client, tenant_a, "admin_a", "pass-a")
    _bootstrap_admin(reporting_client, tenant_b, "admin_b", "pass-b")
    token_a = _login(reporting_client, tenant_a, "admin_a", "pass-a")
    token_b = _login(reporting_client, tenant_b, "admin_b", "pass-b")

    template_resp = reporting_client.post(
        "/api/reporting/outcome-report-templates",
        json={
            "name": "phase18-template",
            "format_default": "PDF",
            "title_template": "Outcome Report count={count}",
            "body_template": "task={task_id} topic={topic}",
            "is_active": True,
        },
        headers=_auth_header(token_a),
    )
    assert template_resp.status_code == 201
    template_id = template_resp.json()["id"]

    list_templates = reporting_client.get(
        "/api/reporting/outcome-report-templates",
        headers=_auth_header(token_a),
    )
    assert list_templates.status_code == 200
    assert any(item["id"] == template_id for item in list_templates.json())

    mission_id = _create_mission(reporting_client, token_a, "phase18-report-mission")
    inspection_template_id = _create_template(reporting_client, token_a, "phase18-report-inspection-template")
    task_id = _create_task(
        reporting_client,
        token_a,
        inspection_template_id,
        "phase18-report-task",
        mission_id=mission_id,
    )
    outcome_resp = reporting_client.post(
        "/api/outcomes/records",
        json={
            "task_id": task_id,
            "source_type": "MANUAL",
            "source_id": "phase18-outcome-source",
            "outcome_type": "DEFECT",
            "payload": {"note": "phase18 reporting"},
        },
        headers=_auth_header(token_a),
    )
    assert outcome_resp.status_code == 201

    pdf_export = reporting_client.post(
        "/api/reporting/outcome-report-exports",
        json={
            "template_id": template_id,
            "report_format": "PDF",
            "task_id": task_id,
            "topic": "defect",
        },
        headers=_auth_header(token_a),
    )
    assert pdf_export.status_code == 201
    assert pdf_export.json()["status"] == "SUCCEEDED"
    pdf_path = Path(pdf_export.json()["file_path"])
    assert pdf_path.exists()
    assert pdf_path.read_bytes().startswith(b"%PDF")

    word_export = reporting_client.post(
        "/api/reporting/outcome-report-exports",
        json={"template_id": template_id, "report_format": "WORD", "task_id": task_id},
        headers=_auth_header(token_a),
    )
    assert word_export.status_code == 201
    assert word_export.json()["status"] == "SUCCEEDED"
    word_path = Path(word_export.json()["file_path"])
    assert word_path.exists()
    with ZipFile(word_path) as docx:
        document_xml = docx.read("word/document.xml")
    assert b"Outcome Report" in document_xml

    export_id = pdf_export.json()["id"]
    get_export = reporting_client.get(
        f"/api/reporting/outcome-report-exports/{export_id}",
        headers=_auth_header(token_a),
    )
    assert get_export.status_code == 200
    cross_tenant_export = reporting_client.get(
        f"/api/reporting/outcome-report-exports/{export_id}",
        headers=_auth_header(token_b),
    )
    assert cross_tenant_export.status_code == 404


def test_outcome_report_retention_lifecycle_and_audit(reporting_client: TestClient) -> None:
    tenant_id = _create_tenant(reporting_client, "reporting-outcome-retention")
    _bootstrap_admin(reporting_client, tenant_id, "admin", "admin-pass")
    token = _login(reporting_client, tenant_id, "admin", "admin-pass")

    template_resp = reporting_client.post(
        "/api/reporting/outcome-report-templates",
        json={
            "name": "phase18-retention-template",
            "format_default": "WORD",
            "title_template": "Retention Report count={count}",
            "body_template": "retention test",
            "is_active": True,
        },
        headers=_auth_header(token),
    )
    assert template_resp.status_code == 201
    template_id = template_resp.json()["id"]

    inspection_template_id = _create_template(reporting_client, token, "phase18-retention-inspection-template")
    task_id = _create_task(reporting_client, token, inspection_template_id, "phase18-retention-task")
    outcome_resp = reporting_client.post(
        "/api/outcomes/records",
        json={
            "task_id": task_id,
            "source_type": "MANUAL",
            "source_id": "phase18-retention-source",
            "outcome_type": "DEFECT",
            "payload": {"note": "retention"},
        },
        headers=_auth_header(token),
    )
    assert outcome_resp.status_code == 201

    export_resp = reporting_client.post(
        "/api/reporting/outcome-report-exports",
        json={"template_id": template_id, "report_format": "WORD", "task_id": task_id},
        headers=_auth_header(token),
    )
    assert export_resp.status_code == 201
    export_id = export_resp.json()["id"]
    export_path = Path(export_resp.json()["file_path"])
    assert export_path.exists()

    with Session(db.engine) as session:
        export_row = session.exec(select(OutcomeReportExport).where(OutcomeReportExport.id == export_id)).first()
        assert export_row is not None
        export_row.completed_at = now_utc() - timedelta(days=10)
        export_row.updated_at = now_utc() - timedelta(days=10)
        session.add(export_row)
        session.commit()

    dry_run_resp = reporting_client.post(
        "/api/reporting/outcome-report-exports:retention",
        json={"retention_days": 3, "dry_run": True},
        headers=_auth_header(token),
    )
    assert dry_run_resp.status_code == 200
    assert dry_run_resp.json()["expired_count"] >= 1
    assert export_path.exists()

    run_resp = reporting_client.post(
        "/api/reporting/outcome-report-exports:retention",
        json={"retention_days": 3, "dry_run": False},
        headers=_auth_header(token),
    )
    assert run_resp.status_code == 200
    assert run_resp.json()["deleted_files"] >= 1
    assert not export_path.exists()

    get_export = reporting_client.get(
        f"/api/reporting/outcome-report-exports/{export_id}",
        headers=_auth_header(token),
    )
    assert get_export.status_code == 200
    assert get_export.json()["file_path"] is None

    with Session(db.engine) as session:
        audit_rows = list(
            session.exec(
                select(AuditLog).where(AuditLog.tenant_id == tenant_id).where(
                    AuditLog.action == "reporting.outcome_report.retention.run"
                )
            ).all()
        )
    assert len(audit_rows) >= 2
