from __future__ import annotations

import asyncio
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

        tenant_id, token = await bootstrap_admin(client, "phase24")

        plan_resp = await client.post(
            "/api/billing/plans",
            json={
                "plan_code": "PHASE24_PRO_M",
                "display_name": "Phase24 Pro Monthly",
                "billing_cycle": "MONTHLY",
                "price_cents": 29900,
                "currency": "CNY",
                "quotas": [
                    {"quota_key": "users", "quota_limit": 50, "enforcement_mode": "HARD_LIMIT"},
                    {"quota_key": "devices", "quota_limit": 120, "enforcement_mode": "SOFT_LIMIT"},
                ],
            },
            headers=auth_headers(token),
        )
        assert_status(plan_resp, 201)
        plan_id = plan_resp.json()["id"]

        sub_resp = await client.post(
            f"/api/billing/tenants/{tenant_id}/subscriptions",
            json={
                "plan_id": plan_id,
                "status": "ACTIVE",
                "auto_renew": True,
                "detail": {"source": "phase24-demo"},
            },
            headers=auth_headers(token),
        )
        assert_status(sub_resp, 201)

        override_resp = await client.put(
            f"/api/billing/tenants/{tenant_id}/quotas/overrides",
            json={
                "overrides": [
                    {
                        "quota_key": "devices",
                        "override_limit": 150,
                        "enforcement_mode": "HARD_LIMIT",
                        "reason": "phase24 demo uplift",
                        "is_active": True,
                    }
                ]
            },
            headers=auth_headers(token),
        )
        assert_status(override_resp, 200)

        ingest_resp_1 = await client.post(
            "/api/billing/usage:ingest",
            json={
                "meter_key": "users",
                "quantity": 10,
                "source_event_id": "phase24-demo-evt-001",
                "detail": {"source": "phase24-demo"},
            },
            headers=auth_headers(token),
        )
        assert_status(ingest_resp_1, 201)
        if ingest_resp_1.json()["deduplicated"] is not False:
            raise RuntimeError("expected first usage ingest not deduplicated")

        ingest_resp_dup = await client.post(
            "/api/billing/usage:ingest",
            json={
                "meter_key": "users",
                "quantity": 10,
                "source_event_id": "phase24-demo-evt-001",
                "detail": {"source": "phase24-demo-dup"},
            },
            headers=auth_headers(token),
        )
        assert_status(ingest_resp_dup, 201)
        if ingest_resp_dup.json()["deduplicated"] is not True:
            raise RuntimeError("expected duplicate usage ingest to deduplicate")

        quota_check_resp = await client.post(
            f"/api/billing/tenants/{tenant_id}/quotas:check",
            json={"meter_key": "users", "quantity": 1},
            headers=auth_headers(token),
        )
        assert_status(quota_check_resp, 200)
        if quota_check_resp.json()["allowed"] is not True:
            raise RuntimeError("expected users quota check to allow in demo")

        now = datetime.now(UTC)
        period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if period_start.month == 12:
            period_end = period_start.replace(year=period_start.year + 1, month=1)
        else:
            period_end = period_start.replace(month=period_start.month + 1)

        invoice_resp = await client.post(
            "/api/billing/invoices:generate",
            json={
                "tenant_id": tenant_id,
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
                "adjustments_cents": 100,
                "force_recompute": True,
                "detail": {"source": "phase24-demo"},
            },
            headers=auth_headers(token),
        )
        assert_status(invoice_resp, 201)
        invoice = invoice_resp.json()
        invoice_id = invoice["id"]

        invoice_detail_resp = await client.get(
            f"/api/billing/invoices/{invoice_id}",
            headers=auth_headers(token),
        )
        assert_status(invoice_detail_resp, 200)
        detail = invoice_detail_resp.json()
        lines_total = sum(line["amount_cents"] for line in detail["lines"])
        subtotal_cents = detail["invoice"]["subtotal_cents"]
        adjustments_cents = detail["invoice"]["adjustments_cents"]
        total_amount_cents = detail["invoice"]["total_amount_cents"]
        if lines_total != subtotal_cents:
            raise RuntimeError(
                f"invoice subtotal mismatch: lines_total={lines_total}, subtotal={subtotal_cents}"
            )
        if subtotal_cents + adjustments_cents != total_amount_cents:
            raise RuntimeError(
                "invoice amount mismatch: "
                f"subtotal={subtotal_cents}, adjustments={adjustments_cents}, total={total_amount_cents}"
            )

        close_resp = await client.post(
            f"/api/billing/invoices/{invoice_id}:close",
            json={"note": "phase24 demo close"},
            headers=auth_headers(token),
        )
        assert_status(close_resp, 200)
        if close_resp.json()["status"] != "CLOSED":
            raise RuntimeError("expected invoice status CLOSED after close")

    print("demo_phase24_billing_quota: ok")


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
