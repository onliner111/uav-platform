"""phase24 wp2 usage quota expand

Revision ID: 202602270098
Revises: 202602270097
Create Date: 2026-02-27
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "202602270098"
down_revision = "202602270097"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "billing_usage_events",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("meter_key", sa.String(length=120), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_event_id", sa.String(length=200), nullable=False),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_billing_usage_events_tenant_id_id"),
        sa.UniqueConstraint(
            "tenant_id",
            "meter_key",
            "source_event_id",
            name="uq_billing_usage_events_tenant_meter_source",
        ),
    )
    op.create_index("ix_billing_usage_events_tenant_id", "billing_usage_events", ["tenant_id"])
    op.create_index("ix_billing_usage_events_meter_key", "billing_usage_events", ["meter_key"])
    op.create_index("ix_billing_usage_events_quantity", "billing_usage_events", ["quantity"])
    op.create_index("ix_billing_usage_events_occurred_at", "billing_usage_events", ["occurred_at"])
    op.create_index(
        "ix_billing_usage_events_source_event_id",
        "billing_usage_events",
        ["source_event_id"],
    )
    op.create_index("ix_billing_usage_events_created_by", "billing_usage_events", ["created_by"])
    op.create_index("ix_billing_usage_events_created_at", "billing_usage_events", ["created_at"])
    op.create_index("ix_billing_usage_events_tenant_id_id", "billing_usage_events", ["tenant_id", "id"])
    op.create_index(
        "ix_billing_usage_events_tenant_meter",
        "billing_usage_events",
        ["tenant_id", "meter_key"],
    )
    op.create_index(
        "ix_billing_usage_events_tenant_occurred",
        "billing_usage_events",
        ["tenant_id", "occurred_at"],
    )

    op.create_table(
        "billing_usage_aggregate_daily",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("meter_key", sa.String(length=120), nullable=False),
        sa.Column("usage_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("total_quantity", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_billing_usage_aggregate_daily_tenant_id_id"),
        sa.UniqueConstraint(
            "tenant_id",
            "meter_key",
            "usage_date",
            name="uq_billing_usage_aggregate_daily_tenant_meter_date",
        ),
    )
    op.create_index(
        "ix_billing_usage_aggregate_daily_tenant_id",
        "billing_usage_aggregate_daily",
        ["tenant_id"],
    )
    op.create_index(
        "ix_billing_usage_aggregate_daily_meter_key",
        "billing_usage_aggregate_daily",
        ["meter_key"],
    )
    op.create_index(
        "ix_billing_usage_aggregate_daily_usage_date",
        "billing_usage_aggregate_daily",
        ["usage_date"],
    )
    op.create_index(
        "ix_billing_usage_aggregate_daily_total_quantity",
        "billing_usage_aggregate_daily",
        ["total_quantity"],
    )
    op.create_index(
        "ix_billing_usage_aggregate_daily_updated_at",
        "billing_usage_aggregate_daily",
        ["updated_at"],
    )
    op.create_index(
        "ix_billing_usage_aggregate_daily_tenant_id_id",
        "billing_usage_aggregate_daily",
        ["tenant_id", "id"],
    )
    op.create_index(
        "ix_billing_usage_aggregate_daily_tenant_meter",
        "billing_usage_aggregate_daily",
        ["tenant_id", "meter_key"],
    )
    op.create_index(
        "ix_billing_usage_aggregate_daily_tenant_date",
        "billing_usage_aggregate_daily",
        ["tenant_id", "usage_date"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_billing_usage_aggregate_daily_tenant_date",
        table_name="billing_usage_aggregate_daily",
    )
    op.drop_index(
        "ix_billing_usage_aggregate_daily_tenant_meter",
        table_name="billing_usage_aggregate_daily",
    )
    op.drop_index(
        "ix_billing_usage_aggregate_daily_tenant_id_id",
        table_name="billing_usage_aggregate_daily",
    )
    op.drop_index(
        "ix_billing_usage_aggregate_daily_updated_at",
        table_name="billing_usage_aggregate_daily",
    )
    op.drop_index(
        "ix_billing_usage_aggregate_daily_total_quantity",
        table_name="billing_usage_aggregate_daily",
    )
    op.drop_index(
        "ix_billing_usage_aggregate_daily_usage_date",
        table_name="billing_usage_aggregate_daily",
    )
    op.drop_index(
        "ix_billing_usage_aggregate_daily_meter_key",
        table_name="billing_usage_aggregate_daily",
    )
    op.drop_index(
        "ix_billing_usage_aggregate_daily_tenant_id",
        table_name="billing_usage_aggregate_daily",
    )
    op.drop_table("billing_usage_aggregate_daily")

    op.drop_index("ix_billing_usage_events_tenant_occurred", table_name="billing_usage_events")
    op.drop_index("ix_billing_usage_events_tenant_meter", table_name="billing_usage_events")
    op.drop_index("ix_billing_usage_events_tenant_id_id", table_name="billing_usage_events")
    op.drop_index("ix_billing_usage_events_created_at", table_name="billing_usage_events")
    op.drop_index("ix_billing_usage_events_created_by", table_name="billing_usage_events")
    op.drop_index("ix_billing_usage_events_source_event_id", table_name="billing_usage_events")
    op.drop_index("ix_billing_usage_events_occurred_at", table_name="billing_usage_events")
    op.drop_index("ix_billing_usage_events_quantity", table_name="billing_usage_events")
    op.drop_index("ix_billing_usage_events_meter_key", table_name="billing_usage_events")
    op.drop_index("ix_billing_usage_events_tenant_id", table_name="billing_usage_events")
    op.drop_table("billing_usage_events")
