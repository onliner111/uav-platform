"""phase24 wp1 billing quota backfill validate

Revision ID: 202602270096
Revises: 202602270095
Create Date: 2026-02-27
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "202602270096"
down_revision = "202602270095"
branch_labels = None
depends_on = None


def _assert_zero(bind: sa.Connection, sql: str, error_message: str) -> None:
    rows = list(bind.execute(sa.text(sql)))
    if rows:
        raise RuntimeError(f"{error_message}. count={len(rows)}")


def upgrade() -> None:
    bind = op.get_bind()
    now = datetime.now(UTC)

    tenant_rows = list(bind.execute(sa.text("SELECT id FROM tenants")).mappings())
    for tenant_row in tenant_rows:
        tenant_id = str(tenant_row["id"])

        plan_rows = list(
            bind.execute(
                sa.text(
                    """
                    SELECT id
                    FROM billing_plan_catalogs
                    WHERE tenant_id = :tenant_id
                    ORDER BY created_at ASC
                    """
                ),
                {"tenant_id": tenant_id},
            ).mappings()
        )
        if not plan_rows:
            plan_id = str(uuid4())
            bind.execute(
                sa.text(
                    """
                    INSERT INTO billing_plan_catalogs
                    (id, tenant_id, plan_code, display_name, description, billing_cycle, price_cents, currency, is_active, created_by, created_at, updated_at)
                    VALUES
                    (:id, :tenant_id, :plan_code, :display_name, :description, :billing_cycle, :price_cents, :currency, :is_active, :created_by, :created_at, :updated_at)
                    """
                ),
                {
                    "id": plan_id,
                    "tenant_id": tenant_id,
                    "plan_code": "DEFAULT",
                    "display_name": "Default Plan",
                    "description": "backfilled default plan for phase24 wp1",
                    "billing_cycle": "MONTHLY",
                    "price_cents": 0,
                    "currency": "CNY",
                    "is_active": True,
                    "created_by": "phase24-backfill",
                    "created_at": now,
                    "updated_at": now,
                },
            )
            plan_rows = [{"id": plan_id}]

        active_sub = bind.execute(
            sa.text(
                """
                SELECT id
                FROM tenant_subscriptions
                WHERE tenant_id = :tenant_id AND status = 'ACTIVE'
                ORDER BY start_at DESC
                LIMIT 1
                """
            ),
            {"tenant_id": tenant_id},
        ).first()
        if active_sub is None:
            plan_id = str(plan_rows[0]["id"])
            bind.execute(
                sa.text(
                    """
                    INSERT INTO tenant_subscriptions
                    (id, tenant_id, plan_id, status, start_at, end_at, auto_renew, detail, created_by, created_at, updated_at)
                    VALUES
                    (:id, :tenant_id, :plan_id, :status, :start_at, :end_at, :auto_renew, :detail, :created_by, :created_at, :updated_at)
                    """
                ),
                {
                    "id": str(uuid4()),
                    "tenant_id": tenant_id,
                    "plan_id": plan_id,
                    "status": "ACTIVE",
                    "start_at": now,
                    "end_at": None,
                    "auto_renew": True,
                    "detail": json.dumps({"source": "phase24_wp1_backfill"}, ensure_ascii=True),
                    "created_by": "phase24-backfill",
                    "created_at": now,
                    "updated_at": now,
                },
            )

    _assert_zero(
        bind,
        """
        SELECT id FROM billing_plan_catalogs WHERE plan_code = ''
        """,
        "Phase24-WP1 validation failed: billing_plan_catalogs.plan_code cannot be empty",
    )
    _assert_zero(
        bind,
        """
        SELECT id FROM billing_plan_quotas WHERE quota_key = ''
        """,
        "Phase24-WP1 validation failed: billing_plan_quotas.quota_key cannot be empty",
    )
    _assert_zero(
        bind,
        """
        SELECT tenant_id
        FROM tenant_subscriptions
        WHERE status = 'ACTIVE'
        GROUP BY tenant_id
        HAVING COUNT(*) > 1
        """,
        "Phase24-WP1 validation failed: multiple ACTIVE subscriptions in one tenant",
    )


def downgrade() -> None:
    # Validation/backfill step only.
    pass
