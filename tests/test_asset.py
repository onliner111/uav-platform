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
def asset_client(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Generator[TestClient, None, None]:
    db_path = tmp_path / "asset_test.db"
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


def _create_drone(client: TestClient, token: str, name: str) -> str:
    response = client.post(
        "/api/registry/drones",
        json={"name": name, "vendor": "FAKE", "capabilities": {"camera": True}},
        headers=_auth_header(token),
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_asset_lifecycle_and_tenant_isolation(asset_client: TestClient) -> None:
    tenant_a = _create_tenant(asset_client, "asset-tenant-a")
    tenant_b = _create_tenant(asset_client, "asset-tenant-b")
    _bootstrap_admin(asset_client, tenant_a, "admin_a", "pass-a")
    _bootstrap_admin(asset_client, tenant_b, "admin_b", "pass-b")
    token_a = _login(asset_client, tenant_a, "admin_a", "pass-a")
    token_b = _login(asset_client, tenant_b, "admin_b", "pass-b")

    drone_a = _create_drone(asset_client, token_a, "drone-asset-a")

    create_resp = asset_client.post(
        "/api/assets",
        json={
            "asset_type": "PAYLOAD",
            "asset_code": "PL-001",
            "name": "payload-main-cam",
            "serial_number": "SN-PL-001",
            "detail": {"weight_kg": 1.2},
        },
        headers=_auth_header(token_a),
    )
    assert create_resp.status_code == 201
    asset_id = create_resp.json()["id"]
    assert create_resp.json()["lifecycle_status"] == "REGISTERED"

    bind_resp = asset_client.post(
        f"/api/assets/{asset_id}/bind",
        json={"bound_to_drone_id": drone_a},
        headers=_auth_header(token_a),
    )
    assert bind_resp.status_code == 200
    assert bind_resp.json()["lifecycle_status"] == "BOUND"
    assert bind_resp.json()["bound_to_drone_id"] == drone_a

    retire_resp = asset_client.post(
        f"/api/assets/{asset_id}/retire",
        json={"reason": "phase09 lifecycle demo"},
        headers=_auth_header(token_a),
    )
    assert retire_resp.status_code == 200
    assert retire_resp.json()["lifecycle_status"] == "RETIRED"
    assert retire_resp.json()["retired_reason"] == "phase09 lifecycle demo"

    cross_get_resp = asset_client.get(f"/api/assets/{asset_id}", headers=_auth_header(token_b))
    assert cross_get_resp.status_code == 404

    list_b = asset_client.get("/api/assets", headers=_auth_header(token_b))
    assert list_b.status_code == 200
    assert list_b.json() == []


def test_asset_filters_and_events(asset_client: TestClient) -> None:
    tenant_id = _create_tenant(asset_client, "asset-events-tenant")
    _bootstrap_admin(asset_client, tenant_id, "admin", "pass")
    token = _login(asset_client, tenant_id, "admin", "pass")
    drone_id = _create_drone(asset_client, token, "drone-filter")

    battery_resp = asset_client.post(
        "/api/assets",
        json={"asset_type": "BATTERY", "asset_code": "BAT-01", "name": "battery-01"},
        headers=_auth_header(token),
    )
    assert battery_resp.status_code == 201
    battery_id = battery_resp.json()["id"]

    payload_resp = asset_client.post(
        "/api/assets",
        json={"asset_type": "PAYLOAD", "asset_code": "PAY-01", "name": "payload-01"},
        headers=_auth_header(token),
    )
    assert payload_resp.status_code == 201
    payload_id = payload_resp.json()["id"]

    bind_resp = asset_client.post(
        f"/api/assets/{battery_id}/bind",
        json={"bound_to_drone_id": drone_id},
        headers=_auth_header(token),
    )
    assert bind_resp.status_code == 200

    retire_resp = asset_client.post(
        f"/api/assets/{payload_id}/retire",
        json={"reason": "retire payload"},
        headers=_auth_header(token),
    )
    assert retire_resp.status_code == 200

    list_type_resp = asset_client.get("/api/assets?asset_type=BATTERY", headers=_auth_header(token))
    assert list_type_resp.status_code == 200
    assert [item["id"] for item in list_type_resp.json()] == [battery_id]

    list_retired_resp = asset_client.get(
        "/api/assets?lifecycle_status=RETIRED",
        headers=_auth_header(token),
    )
    assert list_retired_resp.status_code == 200
    assert [item["id"] for item in list_retired_resp.json()] == [payload_id]

    with Session(db.engine) as session:
        statement = select(EventRecord).where(EventRecord.tenant_id == tenant_id)
        rows = list(session.exec(statement).all())

    event_types = {row.event_type for row in rows if row.event_type.startswith("asset.")}
    assert "asset.registered" in event_types
    assert "asset.bound" in event_types
    assert "asset.retired" in event_types


def test_asset_availability_health_pool_and_cross_tenant(asset_client: TestClient) -> None:
    tenant_a = _create_tenant(asset_client, "asset-avail-tenant-a")
    tenant_b = _create_tenant(asset_client, "asset-avail-tenant-b")
    _bootstrap_admin(asset_client, tenant_a, "admin_a", "pass-a")
    _bootstrap_admin(asset_client, tenant_b, "admin_b", "pass-b")
    token_a = _login(asset_client, tenant_a, "admin_a", "pass-a")
    token_b = _login(asset_client, tenant_b, "admin_b", "pass-b")

    asset_a1_resp = asset_client.post(
        "/api/assets",
        json={"asset_type": "BATTERY", "asset_code": "BAT-A1", "name": "battery-a1"},
        headers=_auth_header(token_a),
    )
    assert asset_a1_resp.status_code == 201
    asset_a1 = asset_a1_resp.json()["id"]

    asset_a2_resp = asset_client.post(
        "/api/assets",
        json={"asset_type": "PAYLOAD", "asset_code": "PAY-A2", "name": "payload-a2"},
        headers=_auth_header(token_a),
    )
    assert asset_a2_resp.status_code == 201
    asset_a2 = asset_a2_resp.json()["id"]

    avail_update_a1 = asset_client.post(
        f"/api/assets/{asset_a1}/availability",
        json={"availability_status": "MAINTENANCE", "region_code": "EAST-1"},
        headers=_auth_header(token_a),
    )
    assert avail_update_a1.status_code == 200
    assert avail_update_a1.json()["availability_status"] == "MAINTENANCE"
    assert avail_update_a1.json()["region_code"] == "EAST-1"

    health_update_a1 = asset_client.post(
        f"/api/assets/{asset_a1}/health",
        json={"health_status": "DEGRADED", "health_score": 58, "detail": {"temp_c": 72}},
        headers=_auth_header(token_a),
    )
    assert health_update_a1.status_code == 200
    assert health_update_a1.json()["health_status"] == "DEGRADED"
    assert health_update_a1.json()["health_score"] == 58

    avail_update_a2 = asset_client.post(
        f"/api/assets/{asset_a2}/availability",
        json={"availability_status": "AVAILABLE", "region_code": "EAST-1"},
        headers=_auth_header(token_a),
    )
    assert avail_update_a2.status_code == 200

    health_update_a2 = asset_client.post(
        f"/api/assets/{asset_a2}/health",
        json={"health_status": "HEALTHY", "health_score": 96},
        headers=_auth_header(token_a),
    )
    assert health_update_a2.status_code == 200

    pool_default = asset_client.get(
        "/api/assets/pool?region_code=EAST-1",
        headers=_auth_header(token_a),
    )
    assert pool_default.status_code == 200
    assert [item["id"] for item in pool_default.json()] == [asset_a2]

    pool_maintenance = asset_client.get(
        "/api/assets/pool?region_code=EAST-1&availability_status=MAINTENANCE",
        headers=_auth_header(token_a),
    )
    assert pool_maintenance.status_code == 200
    assert [item["id"] for item in pool_maintenance.json()] == [asset_a1]

    pool_healthy = asset_client.get(
        "/api/assets/pool?region_code=EAST-1&health_status=HEALTHY&min_health_score=90",
        headers=_auth_header(token_a),
    )
    assert pool_healthy.status_code == 200
    assert [item["id"] for item in pool_healthy.json()] == [asset_a2]

    cross_update = asset_client.post(
        f"/api/assets/{asset_a1}/health",
        json={"health_status": "CRITICAL", "health_score": 10},
        headers=_auth_header(token_b),
    )
    assert cross_update.status_code == 404

    cross_pool = asset_client.get("/api/assets/pool?region_code=EAST-1", headers=_auth_header(token_b))
    assert cross_pool.status_code == 200
    assert cross_pool.json() == []

    retire_a1 = asset_client.post(
        f"/api/assets/{asset_a1}/retire",
        json={"reason": "battery retired"},
        headers=_auth_header(token_a),
    )
    assert retire_a1.status_code == 200

    retired_health_update = asset_client.post(
        f"/api/assets/{asset_a1}/health",
        json={"health_status": "CRITICAL", "health_score": 5},
        headers=_auth_header(token_a),
    )
    assert retired_health_update.status_code == 409


def test_resource_pool_summary_by_region(asset_client: TestClient) -> None:
    tenant_id = _create_tenant(asset_client, "asset-pool-summary-tenant")
    _bootstrap_admin(asset_client, tenant_id, "admin", "pass")
    token = _login(asset_client, tenant_id, "admin", "pass")

    a1_resp = asset_client.post(
        "/api/assets",
        json={"asset_type": "UAV", "asset_code": "UAV-S1", "name": "uav-s1"},
        headers=_auth_header(token),
    )
    assert a1_resp.status_code == 201
    a1 = a1_resp.json()["id"]

    a2_resp = asset_client.post(
        "/api/assets",
        json={"asset_type": "BATTERY", "asset_code": "BAT-S2", "name": "bat-s2"},
        headers=_auth_header(token),
    )
    assert a2_resp.status_code == 201
    a2 = a2_resp.json()["id"]

    a3_resp = asset_client.post(
        "/api/assets",
        json={"asset_type": "PAYLOAD", "asset_code": "PAY-S3", "name": "pay-s3"},
        headers=_auth_header(token),
    )
    assert a3_resp.status_code == 201
    a3 = a3_resp.json()["id"]

    resp = asset_client.post(
        f"/api/assets/{a1}/availability",
        json={"availability_status": "AVAILABLE", "region_code": "R1"},
        headers=_auth_header(token),
    )
    assert resp.status_code == 200
    resp = asset_client.post(
        f"/api/assets/{a1}/health",
        json={"health_status": "HEALTHY", "health_score": 92},
        headers=_auth_header(token),
    )
    assert resp.status_code == 200

    resp = asset_client.post(
        f"/api/assets/{a2}/availability",
        json={"availability_status": "AVAILABLE", "region_code": "R1"},
        headers=_auth_header(token),
    )
    assert resp.status_code == 200
    resp = asset_client.post(
        f"/api/assets/{a2}/health",
        json={"health_status": "DEGRADED", "health_score": 55},
        headers=_auth_header(token),
    )
    assert resp.status_code == 200

    resp = asset_client.post(
        f"/api/assets/{a3}/availability",
        json={"availability_status": "AVAILABLE", "region_code": "R2"},
        headers=_auth_header(token),
    )
    assert resp.status_code == 200
    resp = asset_client.post(
        f"/api/assets/{a3}/health",
        json={"health_status": "HEALTHY", "health_score": 88},
        headers=_auth_header(token),
    )
    assert resp.status_code == 200

    summary_resp = asset_client.get("/api/assets/pool/summary", headers=_auth_header(token))
    assert summary_resp.status_code == 200
    payload = summary_resp.json()
    assert [item["region_code"] for item in payload] == ["R1", "R2"]

    r1 = payload[0]
    assert r1["total_assets"] == 2
    assert r1["available_assets"] == 2
    assert r1["healthy_assets"] == 1
    assert r1["by_type"]["UAV"] == 1
    assert r1["by_type"]["BATTERY"] == 1
    assert r1["average_health_score"] == 73.5

    r2 = payload[1]
    assert r2["total_assets"] == 1
    assert r2["healthy_assets"] == 1
    assert r2["average_health_score"] == 88.0
