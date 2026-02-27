"""phase22 wp3 alert silence sla expand

Revision ID: 202602270089
Revises: 202602270088
Create Date: 2026-02-27
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "202602270089"
down_revision = "202602270088"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "alert_silence_rules",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("alert_type", sa.String(length=50), nullable=True),
        sa.Column("drone_id", sa.String(), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_alert_silence_rules_tenant_id_id"),
    )
    op.create_index("ix_alert_silence_rules_tenant_id", "alert_silence_rules", ["tenant_id"])
    op.create_index("ix_alert_silence_rules_alert_type", "alert_silence_rules", ["alert_type"])
    op.create_index("ix_alert_silence_rules_drone_id", "alert_silence_rules", ["drone_id"])
    op.create_index("ix_alert_silence_rules_starts_at", "alert_silence_rules", ["starts_at"])
    op.create_index("ix_alert_silence_rules_ends_at", "alert_silence_rules", ["ends_at"])
    op.create_index("ix_alert_silence_rules_is_active", "alert_silence_rules", ["is_active"])
    op.create_index("ix_alert_silence_rules_created_by", "alert_silence_rules", ["created_by"])
    op.create_index("ix_alert_silence_rules_created_at", "alert_silence_rules", ["created_at"])
    op.create_index("ix_alert_silence_rules_updated_at", "alert_silence_rules", ["updated_at"])
    op.create_index("ix_alert_silence_rules_tenant_id_id", "alert_silence_rules", ["tenant_id", "id"])
    op.create_index(
        "ix_alert_silence_rules_tenant_active",
        "alert_silence_rules",
        ["tenant_id", "is_active"],
    )

    op.create_table(
        "alert_aggregation_rules",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("alert_type", sa.String(length=50), nullable=True),
        sa.Column("window_seconds", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_alert_aggregation_rules_tenant_id_id"),
        sa.UniqueConstraint("tenant_id", "name", name="uq_alert_aggregation_rules_tenant_name"),
    )
    op.create_index("ix_alert_aggregation_rules_tenant_id", "alert_aggregation_rules", ["tenant_id"])
    op.create_index("ix_alert_aggregation_rules_name", "alert_aggregation_rules", ["name"])
    op.create_index("ix_alert_aggregation_rules_alert_type", "alert_aggregation_rules", ["alert_type"])
    op.create_index(
        "ix_alert_aggregation_rules_window_seconds",
        "alert_aggregation_rules",
        ["window_seconds"],
    )
    op.create_index("ix_alert_aggregation_rules_is_active", "alert_aggregation_rules", ["is_active"])
    op.create_index("ix_alert_aggregation_rules_created_by", "alert_aggregation_rules", ["created_by"])
    op.create_index("ix_alert_aggregation_rules_created_at", "alert_aggregation_rules", ["created_at"])
    op.create_index("ix_alert_aggregation_rules_updated_at", "alert_aggregation_rules", ["updated_at"])
    op.create_index(
        "ix_alert_aggregation_rules_tenant_id_id",
        "alert_aggregation_rules",
        ["tenant_id", "id"],
    )
    op.create_index(
        "ix_alert_aggregation_rules_tenant_active",
        "alert_aggregation_rules",
        ["tenant_id", "is_active"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_alert_aggregation_rules_tenant_active",
        table_name="alert_aggregation_rules",
    )
    op.drop_index(
        "ix_alert_aggregation_rules_tenant_id_id",
        table_name="alert_aggregation_rules",
    )
    op.drop_index("ix_alert_aggregation_rules_updated_at", table_name="alert_aggregation_rules")
    op.drop_index("ix_alert_aggregation_rules_created_at", table_name="alert_aggregation_rules")
    op.drop_index("ix_alert_aggregation_rules_created_by", table_name="alert_aggregation_rules")
    op.drop_index("ix_alert_aggregation_rules_is_active", table_name="alert_aggregation_rules")
    op.drop_index("ix_alert_aggregation_rules_window_seconds", table_name="alert_aggregation_rules")
    op.drop_index("ix_alert_aggregation_rules_alert_type", table_name="alert_aggregation_rules")
    op.drop_index("ix_alert_aggregation_rules_name", table_name="alert_aggregation_rules")
    op.drop_index("ix_alert_aggregation_rules_tenant_id", table_name="alert_aggregation_rules")
    op.drop_table("alert_aggregation_rules")

    op.drop_index(
        "ix_alert_silence_rules_tenant_active",
        table_name="alert_silence_rules",
    )
    op.drop_index(
        "ix_alert_silence_rules_tenant_id_id",
        table_name="alert_silence_rules",
    )
    op.drop_index("ix_alert_silence_rules_updated_at", table_name="alert_silence_rules")
    op.drop_index("ix_alert_silence_rules_created_at", table_name="alert_silence_rules")
    op.drop_index("ix_alert_silence_rules_created_by", table_name="alert_silence_rules")
    op.drop_index("ix_alert_silence_rules_is_active", table_name="alert_silence_rules")
    op.drop_index("ix_alert_silence_rules_ends_at", table_name="alert_silence_rules")
    op.drop_index("ix_alert_silence_rules_starts_at", table_name="alert_silence_rules")
    op.drop_index("ix_alert_silence_rules_drone_id", table_name="alert_silence_rules")
    op.drop_index("ix_alert_silence_rules_alert_type", table_name="alert_silence_rules")
    op.drop_index("ix_alert_silence_rules_tenant_id", table_name="alert_silence_rules")
    op.drop_table("alert_silence_rules")
