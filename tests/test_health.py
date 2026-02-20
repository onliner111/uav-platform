from __future__ import annotations

from fastapi.testclient import TestClient

from app import main as app_main


def test_healthz_ok() -> None:
    client = TestClient(app_main.app)
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readyz_ok_when_dependencies_ready(monkeypatch) -> None:
    monkeypatch.setattr(app_main, "check_db_ready", lambda: True)
    monkeypatch.setattr(app_main, "check_redis_ready", lambda: True)
    client = TestClient(app_main.app)
    response = client.get("/readyz")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"

