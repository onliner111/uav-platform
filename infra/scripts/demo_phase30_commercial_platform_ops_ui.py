from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
from datetime import UTC, datetime

import httpx
from demo_common import assert_status, auth_headers, bootstrap_admin, wait_ok


async def _run() -> None:
    base_url = os.getenv("APP_BASE_URL", "http://app:8000").rstrip("/")
    timeout = httpx.Timeout(20.0)
    async with httpx.AsyncClient(base_url=base_url, timeout=timeout) as client:
        await wait_ok(client, "/healthz")
        await wait_ok(client, "/readyz")

        tenant_id, token = await bootstrap_admin(client, "phase30")

        create_plan_resp = await client.post(
            "/api/billing/plans",
            json={
                "plan_code": "PH30_PRO_M",
                "display_name": "Phase30 Pro Monthly",
                "billing_cycle": "MONTHLY",
                "price_cents": 299900,
                "currency": "CNY",
                "is_active": True,
                "quotas": [
                    {"quota_key": "users", "quota_limit": 5, "enforcement_mode": "HARD_LIMIT"},
                    {"quota_key": "devices", "quota_limit": 20, "enforcement_mode": "SOFT_LIMIT"},
                ],
            },
            headers=auth_headers(token),
        )
        assert_status(create_plan_resp, 201)
        plan_id = create_plan_resp.json()["id"]

        list_plans_resp = await client.get("/api/billing/plans?plan_code=PH30_PRO_M", headers=auth_headers(token))
        assert_status(list_plans_resp, 200)
        if not any(item["id"] == plan_id for item in list_plans_resp.json()):
            raise RuntimeError("phase30 demo expected created billing plan in list API")

        create_sub_resp = await client.post(
            f"/api/billing/tenants/{tenant_id}/subscriptions",
            json={"plan_id": plan_id, "status": "ACTIVE", "auto_renew": True, "detail": {"source": "phase30-demo"}},
            headers=auth_headers(token),
        )
        assert_status(create_sub_resp, 201)
        subscription_id = create_sub_resp.json()["id"]

        override_resp = await client.put(
            f"/api/billing/tenants/{tenant_id}/quotas/overrides",
            json={
                "overrides": [
                    {
                        "quota_key": "devices",
                        "override_limit": 30,
                        "enforcement_mode": "SOFT_LIMIT",
                        "reason": "phase30 uplift",
                        "is_active": True,
                    }
                ]
            },
            headers=auth_headers(token),
        )
        assert_status(override_resp, 200)

        quota_snapshot_resp = await client.get(f"/api/billing/tenants/{tenant_id}/quotas", headers=auth_headers(token))
        assert_status(quota_snapshot_resp, 200)
        quota_snapshot = quota_snapshot_resp.json()
        if quota_snapshot["subscription_id"] != subscription_id:
            raise RuntimeError("phase30 demo expected quota snapshot bound to active subscription")

        ingest_usage_resp = await client.post(
            "/api/billing/usage:ingest",
            json={
                "meter_key": "users",
                "quantity": 5,
                "source_event_id": "phase30-users-001",
                "detail": {"source": "phase30-demo"},
            },
            headers=auth_headers(token),
        )
        assert_status(ingest_usage_resp, 201)
        if ingest_usage_resp.json()["deduplicated"] is not False:
            raise RuntimeError("phase30 demo expected first usage event non-deduplicated")

        usage_summary_resp = await client.get(
            f"/api/billing/tenants/{tenant_id}/usage/summary?meter_key=users",
            headers=auth_headers(token),
        )
        assert_status(usage_summary_resp, 200)
        if not usage_summary_resp.json():
            raise RuntimeError("phase30 demo expected usage summary rows")

        quota_check_resp = await client.post(
            f"/api/billing/tenants/{tenant_id}/quotas:check",
            json={"meter_key": "users", "quantity": 1},
            headers=auth_headers(token),
        )
        assert_status(quota_check_resp, 200)
        quota_check = quota_check_resp.json()
        if quota_check["allowed"] is not False:
            raise RuntimeError("phase30 demo expected hard limit quota check blocked")

        now = datetime.now(UTC)
        period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if period_start.month == 12:
            period_end = period_start.replace(year=period_start.year + 1, month=1)
        else:
            period_end = period_start.replace(month=period_start.month + 1)

        generate_invoice_resp = await client.post(
            "/api/billing/invoices:generate",
            json={
                "tenant_id": tenant_id,
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
                "adjustments_cents": 100,
                "force_recompute": True,
                "detail": {"source": "phase30-demo"},
            },
            headers=auth_headers(token),
        )
        assert_status(generate_invoice_resp, 201)
        invoice_id = generate_invoice_resp.json()["id"]

        invoice_detail_resp = await client.get(f"/api/billing/invoices/{invoice_id}", headers=auth_headers(token))
        assert_status(invoice_detail_resp, 200)
        if invoice_detail_resp.json()["invoice"]["id"] != invoice_id:
            raise RuntimeError("phase30 demo expected invoice detail id matched")

        close_invoice_resp = await client.post(
            f"/api/billing/invoices/{invoice_id}:close",
            json={"note": "phase30 close"},
            headers=auth_headers(token),
        )
        assert_status(close_invoice_resp, 200)
        if close_invoice_resp.json()["status"] != "CLOSED":
            raise RuntimeError("phase30 demo expected invoice closed")

        credential_suffix = tenant_id.split("-")[0]
        credential_key_id = f"phase30-key-{credential_suffix}"
        credential_api_key = f"phase30-api-key-{credential_suffix}"
        credential_signing_secret = f"phase30-signing-secret-{credential_suffix}"

        credential_resp = await client.post(
            "/api/open-platform/credentials",
            json={
                "key_id": credential_key_id,
                "api_key": credential_api_key,
                "signing_secret": credential_signing_secret,
            },
            headers=auth_headers(token),
        )
        assert_status(credential_resp, 201)
        credential = credential_resp.json()
        if credential["key_id"] != credential_key_id:
            raise RuntimeError("phase30 demo expected created credential key_id matched")

        credentials_resp = await client.get("/api/open-platform/credentials", headers=auth_headers(token))
        assert_status(credentials_resp, 200)
        if not any(item["id"] == credential["id"] for item in credentials_resp.json()):
            raise RuntimeError("phase30 demo expected credential in list API")

        webhook_resp = await client.post(
            "/api/open-platform/webhooks",
            json={
                "name": "phase30-hook",
                "endpoint_url": "https://external.example/phase30/hook",
                "event_type": "workorder.upsert",
                "credential_id": credential["id"],
            },
            headers=auth_headers(token),
        )
        assert_status(webhook_resp, 201)
        endpoint_id = webhook_resp.json()["id"]

        webhooks_resp = await client.get("/api/open-platform/webhooks", headers=auth_headers(token))
        assert_status(webhooks_resp, 200)
        if not any(item["id"] == endpoint_id for item in webhooks_resp.json()):
            raise RuntimeError("phase30 demo expected webhook in list API")

        dispatch_resp = await client.post(
            f"/api/open-platform/webhooks/{endpoint_id}/dispatch-test",
            json={"payload": {"ticket_id": "PH30-001"}},
            headers=auth_headers(token),
        )
        assert_status(dispatch_resp, 200)
        if dispatch_resp.json()["status"] != "SENT":
            raise RuntimeError("phase30 demo expected webhook dispatch status SENT")

        ingress_payload = {"event_type": "workorder.upsert", "payload": {"ticket_id": "PH30-001"}}
        raw_body = json.dumps(ingress_payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
        signature = hmac.new(credential_signing_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()

        adapter_ingest_resp = await client.post(
            "/api/open-platform/adapters/events/ingest",
            content=raw_body,
            headers={
                "Content-Type": "application/json",
                "X-Open-Key-Id": credential_key_id,
                "X-Open-Api-Key": credential_api_key,
                "X-Open-Signature": signature,
            },
        )
        assert_status(adapter_ingest_resp, 201)
        if adapter_ingest_resp.json()["status"] != "ACCEPTED":
            raise RuntimeError("phase30 demo expected adapter event accepted")

        adapter_events_resp = await client.get("/api/open-platform/adapters/events", headers=auth_headers(token))
        assert_status(adapter_events_resp, 200)
        if not any(item["status"] == "ACCEPTED" for item in adapter_events_resp.json()):
            raise RuntimeError("phase30 demo expected accepted adapter event in list API")

        ui_checks = [
            ("/ui/commercial-ops", "Billing + Quota Operations"),
            ("/ui/commercial-ops", "Usage + Invoice Governance"),
            ("/ui/open-platform", "Open Platform Access + Webhook Ops"),
            ("/ui/open-platform", "Dispatch + Adapter Ingress"),
        ]
        for path, expected_text in ui_checks:
            response = await client.get(f"{path}?token={token}")
            assert_status(response, 200)
            if expected_text not in response.text:
                raise RuntimeError(f"phase30 demo expected '{expected_text}' in {path}")

    print("demo_phase30_commercial_platform_ops_ui: ok")


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
