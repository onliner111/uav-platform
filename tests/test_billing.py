from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlmodel import SQLModel, create_engine

from app import main as app_main
from app.infra import audit, db, events


@pytest.fixture()
def billing_client(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Generator[TestClient, None, None]:
    db_path = tmp_path / "billing_test.db"
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


def test_billing_wp1_plan_subscription_override_chain(billing_client: TestClient) -> None:
    tenant_id = _create_tenant(billing_client, "phase24-billing")
    _bootstrap_admin(billing_client, tenant_id, "admin-billing", "admin-pass")
    token = _login(billing_client, tenant_id, "admin-billing", "admin-pass")

    create_plan_resp = billing_client.post(
        "/api/billing/plans",
        json={
            "plan_code": "PRO_M",
            "display_name": "Pro Monthly",
            "billing_cycle": "MONTHLY",
            "price_cents": 199900,
            "currency": "CNY",
            "is_active": True,
            "quotas": [
                {"quota_key": "users", "quota_limit": 50, "enforcement_mode": "HARD_LIMIT"},
                {"quota_key": "devices", "quota_limit": 120, "enforcement_mode": "SOFT_LIMIT"},
            ],
        },
        headers=_auth_header(token),
    )
    assert create_plan_resp.status_code == 201
    plan = create_plan_resp.json()
    plan_id = plan["id"]
    assert plan["plan_code"] == "PRO_M"
    assert len(plan["quotas"]) == 2

    list_plans_resp = billing_client.get(
        "/api/billing/plans?plan_code=PRO_M",
        headers=_auth_header(token),
    )
    assert list_plans_resp.status_code == 200
    listed = list_plans_resp.json()
    assert len(listed) == 1
    assert listed[0]["id"] == plan_id

    create_sub_resp = billing_client.post(
        f"/api/billing/tenants/{tenant_id}/subscriptions",
        json={
            "plan_id": plan_id,
            "status": "ACTIVE",
            "auto_renew": True,
            "detail": {"source": "phase24-wp1-test"},
        },
        headers=_auth_header(token),
    )
    assert create_sub_resp.status_code == 201
    sub_id = create_sub_resp.json()["id"]

    duplicate_active_resp = billing_client.post(
        f"/api/billing/tenants/{tenant_id}/subscriptions",
        json={
            "plan_id": plan_id,
            "status": "ACTIVE",
            "auto_renew": True,
        },
        headers=_auth_header(token),
    )
    assert duplicate_active_resp.status_code == 409

    suspended_sub_resp = billing_client.post(
        f"/api/billing/tenants/{tenant_id}/subscriptions",
        json={
            "plan_id": plan_id,
            "status": "SUSPENDED",
            "auto_renew": False,
        },
        headers=_auth_header(token),
    )
    assert suspended_sub_resp.status_code == 201

    list_subs_resp = billing_client.get(
        f"/api/billing/tenants/{tenant_id}/subscriptions",
        headers=_auth_header(token),
    )
    assert list_subs_resp.status_code == 200
    subs = list_subs_resp.json()
    assert len(subs) == 2
    assert any(item["id"] == sub_id and item["status"] == "ACTIVE" for item in subs)

    upsert_override_resp = billing_client.put(
        f"/api/billing/tenants/{tenant_id}/quotas/overrides",
        json={
            "overrides": [
                {
                    "quota_key": "devices",
                    "override_limit": 150,
                    "enforcement_mode": "HARD_LIMIT",
                    "reason": "pilot expansion",
                    "is_active": True,
                },
                {
                    "quota_key": "storage_bytes",
                    "override_limit": 1099511627776,
                    "enforcement_mode": "SOFT_LIMIT",
                    "reason": "temporary uplift",
                    "is_active": True,
                },
            ]
        },
        headers=_auth_header(token),
    )
    assert upsert_override_resp.status_code == 200
    overrides = upsert_override_resp.json()
    assert len(overrides) == 2

    quota_snapshot_resp = billing_client.get(
        f"/api/billing/tenants/{tenant_id}/quotas",
        headers=_auth_header(token),
    )
    assert quota_snapshot_resp.status_code == 200
    snapshot = quota_snapshot_resp.json()
    assert snapshot["subscription_id"] == sub_id
    effective = {item["quota_key"]: item for item in snapshot["quotas"]}
    assert effective["users"]["quota_limit"] == 50
    assert effective["users"]["source"] == "PLAN"
    assert effective["devices"]["quota_limit"] == 150
    assert effective["devices"]["source"] == "OVERRIDE"
    assert effective["storage_bytes"]["quota_limit"] == 1099511627776
    assert effective["storage_bytes"]["source"] == "OVERRIDE"

    ingest_first = billing_client.post(
        "/api/billing/usage:ingest",
        json={
            "meter_key": "users",
            "quantity": 40,
            "source_event_id": "evt-users-001",
            "detail": {"source": "wp2-test"},
        },
        headers=_auth_header(token),
    )
    assert ingest_first.status_code == 201
    assert ingest_first.json()["deduplicated"] is False

    ingest_duplicate = billing_client.post(
        "/api/billing/usage:ingest",
        json={
            "meter_key": "users",
            "quantity": 40,
            "source_event_id": "evt-users-001",
            "detail": {"source": "wp2-test-dup"},
        },
        headers=_auth_header(token),
    )
    assert ingest_duplicate.status_code == 201
    assert ingest_duplicate.json()["deduplicated"] is True

    ingest_second = billing_client.post(
        "/api/billing/usage:ingest",
        json={
            "meter_key": "users",
            "quantity": 15,
            "source_event_id": "evt-users-002",
            "detail": {"source": "wp2-test"},
        },
        headers=_auth_header(token),
    )
    assert ingest_second.status_code == 201
    assert ingest_second.json()["deduplicated"] is False

    usage_summary_resp = billing_client.get(
        f"/api/billing/tenants/{tenant_id}/usage/summary?meter_key=users",
        headers=_auth_header(token),
    )
    assert usage_summary_resp.status_code == 200
    summary_rows = usage_summary_resp.json()
    assert len(summary_rows) == 1
    assert summary_rows[0]["meter_key"] == "users"
    assert summary_rows[0]["total_quantity"] == 55

    hard_limit_check = billing_client.post(
        f"/api/billing/tenants/{tenant_id}/quotas:check",
        json={"meter_key": "users", "quantity": 1},
        headers=_auth_header(token),
    )
    assert hard_limit_check.status_code == 200
    hard_body = hard_limit_check.json()
    assert hard_body["allowed"] is False
    assert hard_body["reason"] == "hard_limit_exceeded"
    assert hard_body["projected_quantity"] == 56

    no_rule_check = billing_client.post(
        f"/api/billing/tenants/{tenant_id}/quotas:check",
        json={"meter_key": "unknown_meter", "quantity": 3},
        headers=_auth_header(token),
    )
    assert no_rule_check.status_code == 200
    no_rule_body = no_rule_check.json()
    assert no_rule_body["allowed"] is True
    assert no_rule_body["source"] == "NO_RULE"
    assert no_rule_body["reason"] == "quota_not_configured"

    now = datetime.now(UTC)
    period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if period_start.month == 12:
        period_end = period_start.replace(year=period_start.year + 1, month=1)
    else:
        period_end = period_start.replace(month=period_start.month + 1)

    generate_invoice_resp = billing_client.post(
        "/api/billing/invoices:generate",
        json={
            "tenant_id": tenant_id,
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "adjustments_cents": 100,
            "force_recompute": True,
        },
        headers=_auth_header(token),
    )
    assert generate_invoice_resp.status_code == 201
    invoice = generate_invoice_resp.json()
    invoice_id = invoice["id"]
    assert invoice["status"] == "DRAFT"
    assert invoice["total_amount_cents"] >= invoice["subtotal_cents"]

    list_invoices_resp = billing_client.get(
        f"/api/billing/tenants/{tenant_id}/invoices",
        headers=_auth_header(token),
    )
    assert list_invoices_resp.status_code == 200
    assert any(item["id"] == invoice_id for item in list_invoices_resp.json())

    invoice_detail_resp = billing_client.get(
        f"/api/billing/invoices/{invoice_id}",
        headers=_auth_header(token),
    )
    assert invoice_detail_resp.status_code == 200
    detail = invoice_detail_resp.json()
    line_types = {item["line_type"] for item in detail["lines"]}
    assert "PLAN_BASE" in line_types
    assert "USAGE" in line_types

    close_invoice_resp = billing_client.post(
        f"/api/billing/invoices/{invoice_id}:close",
        json={"note": "close for month settlement"},
        headers=_auth_header(token),
    )
    assert close_invoice_resp.status_code == 200
    assert close_invoice_resp.json()["status"] == "CLOSED"

    regenerate_closed_resp = billing_client.post(
        "/api/billing/invoices:generate",
        json={
            "tenant_id": tenant_id,
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "adjustments_cents": 0,
            "force_recompute": True,
        },
        headers=_auth_header(token),
    )
    assert regenerate_closed_resp.status_code == 409

    void_closed_resp = billing_client.post(
        f"/api/billing/invoices/{invoice_id}:void",
        json={"reason": "try void closed"},
        headers=_auth_header(token),
    )
    assert void_closed_resp.status_code == 409


def test_billing_wp1_tenant_boundary_enforced(billing_client: TestClient) -> None:
    tenant_a = _create_tenant(billing_client, "phase24-billing-a")
    _bootstrap_admin(billing_client, tenant_a, "admin-a", "admin-pass")
    token_a = _login(billing_client, tenant_a, "admin-a", "admin-pass")

    tenant_b = _create_tenant(billing_client, "phase24-billing-b")
    _bootstrap_admin(billing_client, tenant_b, "admin-b", "admin-pass")
    token_b = _login(billing_client, tenant_b, "admin-b", "admin-pass")

    create_plan_resp = billing_client.post(
        "/api/billing/plans",
        json={
            "plan_code": "BASIC_M",
            "display_name": "Basic Monthly",
            "billing_cycle": "MONTHLY",
            "price_cents": 0,
            "currency": "CNY",
        },
        headers=_auth_header(token_a),
    )
    assert create_plan_resp.status_code == 201

    denied_list_subs = billing_client.get(
        f"/api/billing/tenants/{tenant_a}/subscriptions",
        headers=_auth_header(token_b),
    )
    assert denied_list_subs.status_code == 404

    denied_override = billing_client.put(
        f"/api/billing/tenants/{tenant_a}/quotas/overrides",
        json={
            "overrides": [
                {
                    "quota_key": "users",
                    "override_limit": 999,
                    "enforcement_mode": "HARD_LIMIT",
                    "is_active": True,
                }
            ]
        },
        headers=_auth_header(token_b),
    )
    assert denied_override.status_code == 404

    denied_usage_summary = billing_client.get(
        f"/api/billing/tenants/{tenant_a}/usage/summary",
        headers=_auth_header(token_b),
    )
    assert denied_usage_summary.status_code == 404

    denied_quota_check = billing_client.post(
        f"/api/billing/tenants/{tenant_a}/quotas:check",
        json={"meter_key": "users", "quantity": 1},
        headers=_auth_header(token_b),
    )
    assert denied_quota_check.status_code == 404

    denied_invoice_generate = billing_client.post(
        "/api/billing/invoices:generate",
        json={
            "tenant_id": tenant_a,
            "period_start": "2026-02-01T00:00:00+00:00",
            "period_end": "2026-03-01T00:00:00+00:00",
            "force_recompute": True,
        },
        headers=_auth_header(token_b),
    )
    assert denied_invoice_generate.status_code == 404
