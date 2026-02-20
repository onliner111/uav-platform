from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select

from app import main as app_main
from app.domain.models import EventRecord
from app.infra import audit, db, events, redis_state


class FakeRedis:
    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    def set(self, key: str, value: str) -> bool:
        self._store[key] = value
        return True

    def get(self, key: str) -> str | None:
        return self._store.get(key)

    def ping(self) -> bool:
        return True


@pytest.fixture()
def alert_client(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Generator[TestClient, None, None]:
    db_path = tmp_path / "alert_test.db"
    test_engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(test_engine)
    fake_redis = FakeRedis()

    monkeypatch.setattr(db, "engine", test_engine)
    monkeypatch.setattr(audit, "engine", test_engine)
    monkeypatch.setattr(events, "engine", test_engine)
    monkeypatch.setattr(redis_state, "get_redis", lambda: fake_redis)

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


def _ingest_payload(
    drone_id: str,
    *,
    battery_percent: float,
    link_lost: bool = False,
    geofence_breach: bool = False,
) -> dict[str, object]:
    return {
        "tenant_id": "spoofed",
        "drone_id": drone_id,
        "position": {"lat": 30.123, "lon": 114.456, "alt_m": 120.5},
        "battery": {"percent": battery_percent},
        "link": {"latency_ms": 3000 if link_lost else 50},
        "mode": "LINK_LOST" if link_lost else "AUTO",
        "health": {
            "low_battery": battery_percent <= 20.0,
            "link_lost": link_lost,
            "geofence_breach": geofence_breach,
        },
    }


def test_alert_generated_from_telemetry_and_lifecycle(alert_client: TestClient) -> None:
    tenant_id = _create_tenant(alert_client, "alert-tenant")
    _bootstrap_admin(alert_client, tenant_id, "admin", "admin-pass")
    token = _login(alert_client, tenant_id, "admin", "admin-pass")

    ingest_resp = alert_client.post(
        "/api/telemetry/ingest",
        json=_ingest_payload("drone-alert-1", battery_percent=12.0),
        headers=_auth_header(token),
    )
    assert ingest_resp.status_code == 200

    list_resp = alert_client.get("/api/alert/alerts", headers=_auth_header(token))
    assert list_resp.status_code == 200
    alerts = list_resp.json()
    assert len(alerts) == 1
    alert_id = alerts[0]["id"]
    assert alerts[0]["alert_type"] == "LOW_BATTERY"
    assert alerts[0]["status"] == "OPEN"

    second_ingest = alert_client.post(
        "/api/telemetry/ingest",
        json=_ingest_payload("drone-alert-1", battery_percent=11.0),
        headers=_auth_header(token),
    )
    assert second_ingest.status_code == 200
    list_again = alert_client.get("/api/alert/alerts", headers=_auth_header(token))
    assert list_again.status_code == 200
    assert len(list_again.json()) == 1

    ack_resp = alert_client.post(
        f"/api/alert/alerts/{alert_id}/ack",
        json={"comment": "operator acknowledged"},
        headers=_auth_header(token),
    )
    assert ack_resp.status_code == 200
    assert ack_resp.json()["status"] == "ACKED"

    close_resp = alert_client.post(
        f"/api/alert/alerts/{alert_id}/close",
        json={"comment": "handled"},
        headers=_auth_header(token),
    )
    assert close_resp.status_code == 200
    assert close_resp.json()["status"] == "CLOSED"

    with Session(db.engine) as session:
        rows = list(session.exec(select(EventRecord).where(EventRecord.tenant_id == tenant_id)).all())
    related = [row for row in rows if row.payload.get("alert_id") == alert_id]
    event_types = {row.event_type for row in related}
    assert "alert.created" in event_types
    assert "alert.acked" in event_types
    assert "alert.closed" in event_types


def test_alert_rules_link_loss_and_geofence(alert_client: TestClient) -> None:
    tenant_id = _create_tenant(alert_client, "alert-rules-tenant")
    _bootstrap_admin(alert_client, tenant_id, "admin", "admin-pass")
    token = _login(alert_client, tenant_id, "admin", "admin-pass")

    ingest_resp = alert_client.post(
        "/api/telemetry/ingest",
        json=_ingest_payload(
            "drone-alert-2",
            battery_percent=88.0,
            link_lost=True,
            geofence_breach=True,
        ),
        headers=_auth_header(token),
    )
    assert ingest_resp.status_code == 200

    list_resp = alert_client.get("/api/alert/alerts", headers=_auth_header(token))
    assert list_resp.status_code == 200
    alert_types = {item["alert_type"] for item in list_resp.json()}
    assert "LINK_LOSS" in alert_types
    assert "GEOFENCE_BREACH" in alert_types
