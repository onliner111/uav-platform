"""phase24 wp1 billing quota expand

Revision ID: 202602270095
Revises: 202602270094
Create Date: 2026-02-27
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "202602270095"
down_revision = "202602270094"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "billing_plan_catalogs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("plan_code", sa.String(length=80), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("billing_cycle", sa.String(length=20), nullable=False),
        sa.Column("price_cents", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("currency", sa.String(length=20), nullable=False, server_default="CNY"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_billing_plan_catalogs_tenant_id_id"),
        sa.UniqueConstraint("tenant_id", "plan_code", name="uq_billing_plan_catalogs_tenant_plan_code"),
    )
    op.create_index("ix_billing_plan_catalogs_tenant_id", "billing_plan_catalogs", ["tenant_id"])
    op.create_index("ix_billing_plan_catalogs_plan_code", "billing_plan_catalogs", ["plan_code"])
    op.create_index("ix_billing_plan_catalogs_display_name", "billing_plan_catalogs", ["display_name"])
    op.create_index("ix_billing_plan_catalogs_billing_cycle", "billing_plan_catalogs", ["billing_cycle"])
    op.create_index("ix_billing_plan_catalogs_currency", "billing_plan_catalogs", ["currency"])
    op.create_index("ix_billing_plan_catalogs_is_active", "billing_plan_catalogs", ["is_active"])
    op.create_index("ix_billing_plan_catalogs_created_by", "billing_plan_catalogs", ["created_by"])
    op.create_index("ix_billing_plan_catalogs_created_at", "billing_plan_catalogs", ["created_at"])
    op.create_index("ix_billing_plan_catalogs_updated_at", "billing_plan_catalogs", ["updated_at"])
    op.create_index("ix_billing_plan_catalogs_tenant_id_id", "billing_plan_catalogs", ["tenant_id", "id"])
    op.create_index(
        "ix_billing_plan_catalogs_tenant_plan_code",
        "billing_plan_catalogs",
        ["tenant_id", "plan_code"],
    )
    op.create_index(
        "ix_billing_plan_catalogs_tenant_cycle",
        "billing_plan_catalogs",
        ["tenant_id", "billing_cycle"],
    )
    op.create_index(
        "ix_billing_plan_catalogs_tenant_active",
        "billing_plan_catalogs",
        ["tenant_id", "is_active"],
    )

    op.create_table(
        "billing_plan_quotas",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("plan_id", sa.String(), nullable=False),
        sa.Column("quota_key", sa.String(length=120), nullable=False),
        sa.Column("quota_limit", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("enforcement_mode", sa.String(length=20), nullable=False),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_billing_plan_quotas_tenant_id_id"),
        sa.UniqueConstraint(
            "tenant_id",
            "plan_id",
            "quota_key",
            name="uq_billing_plan_quotas_tenant_plan_key",
        ),
    )
    op.create_index("ix_billing_plan_quotas_tenant_id", "billing_plan_quotas", ["tenant_id"])
    op.create_index("ix_billing_plan_quotas_plan_id", "billing_plan_quotas", ["plan_id"])
    op.create_index("ix_billing_plan_quotas_quota_key", "billing_plan_quotas", ["quota_key"])
    op.create_index(
        "ix_billing_plan_quotas_enforcement_mode",
        "billing_plan_quotas",
        ["enforcement_mode"],
    )
    op.create_index("ix_billing_plan_quotas_created_at", "billing_plan_quotas", ["created_at"])
    op.create_index("ix_billing_plan_quotas_updated_at", "billing_plan_quotas", ["updated_at"])
    op.create_index("ix_billing_plan_quotas_tenant_id_id", "billing_plan_quotas", ["tenant_id", "id"])
    op.create_index("ix_billing_plan_quotas_tenant_plan", "billing_plan_quotas", ["tenant_id", "plan_id"])
    op.create_index("ix_billing_plan_quotas_tenant_key", "billing_plan_quotas", ["tenant_id", "quota_key"])

    op.create_table(
        "tenant_subscriptions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("plan_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("auto_renew", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_tenant_subscriptions_tenant_id_id"),
    )
    op.create_index("ix_tenant_subscriptions_tenant_id", "tenant_subscriptions", ["tenant_id"])
    op.create_index("ix_tenant_subscriptions_plan_id", "tenant_subscriptions", ["plan_id"])
    op.create_index("ix_tenant_subscriptions_status", "tenant_subscriptions", ["status"])
    op.create_index("ix_tenant_subscriptions_start_at", "tenant_subscriptions", ["start_at"])
    op.create_index("ix_tenant_subscriptions_end_at", "tenant_subscriptions", ["end_at"])
    op.create_index("ix_tenant_subscriptions_auto_renew", "tenant_subscriptions", ["auto_renew"])
    op.create_index("ix_tenant_subscriptions_created_by", "tenant_subscriptions", ["created_by"])
    op.create_index("ix_tenant_subscriptions_created_at", "tenant_subscriptions", ["created_at"])
    op.create_index("ix_tenant_subscriptions_updated_at", "tenant_subscriptions", ["updated_at"])
    op.create_index("ix_tenant_subscriptions_tenant_id_id", "tenant_subscriptions", ["tenant_id", "id"])
    op.create_index("ix_tenant_subscriptions_tenant_plan", "tenant_subscriptions", ["tenant_id", "plan_id"])
    op.create_index(
        "ix_tenant_subscriptions_tenant_status",
        "tenant_subscriptions",
        ["tenant_id", "status"],
    )
    op.create_index(
        "ix_tenant_subscriptions_tenant_start",
        "tenant_subscriptions",
        ["tenant_id", "start_at"],
    )

    op.create_table(
        "tenant_quota_overrides",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("quota_key", sa.String(length=120), nullable=False),
        sa.Column("override_limit", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("enforcement_mode", sa.String(length=20), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.Column("updated_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_tenant_quota_overrides_tenant_id_id"),
        sa.UniqueConstraint(
            "tenant_id",
            "quota_key",
            name="uq_tenant_quota_overrides_tenant_quota_key",
        ),
    )
    op.create_index("ix_tenant_quota_overrides_tenant_id", "tenant_quota_overrides", ["tenant_id"])
    op.create_index("ix_tenant_quota_overrides_quota_key", "tenant_quota_overrides", ["quota_key"])
    op.create_index(
        "ix_tenant_quota_overrides_enforcement_mode",
        "tenant_quota_overrides",
        ["enforcement_mode"],
    )
    op.create_index("ix_tenant_quota_overrides_is_active", "tenant_quota_overrides", ["is_active"])
    op.create_index("ix_tenant_quota_overrides_updated_by", "tenant_quota_overrides", ["updated_by"])
    op.create_index("ix_tenant_quota_overrides_created_at", "tenant_quota_overrides", ["created_at"])
    op.create_index("ix_tenant_quota_overrides_updated_at", "tenant_quota_overrides", ["updated_at"])
    op.create_index(
        "ix_tenant_quota_overrides_tenant_id_id",
        "tenant_quota_overrides",
        ["tenant_id", "id"],
    )
    op.create_index(
        "ix_tenant_quota_overrides_tenant_key",
        "tenant_quota_overrides",
        ["tenant_id", "quota_key"],
    )
    op.create_index(
        "ix_tenant_quota_overrides_tenant_active",
        "tenant_quota_overrides",
        ["tenant_id", "is_active"],
    )


def downgrade() -> None:
    op.drop_index("ix_tenant_quota_overrides_tenant_active", table_name="tenant_quota_overrides")
    op.drop_index("ix_tenant_quota_overrides_tenant_key", table_name="tenant_quota_overrides")
    op.drop_index("ix_tenant_quota_overrides_tenant_id_id", table_name="tenant_quota_overrides")
    op.drop_index("ix_tenant_quota_overrides_updated_at", table_name="tenant_quota_overrides")
    op.drop_index("ix_tenant_quota_overrides_created_at", table_name="tenant_quota_overrides")
    op.drop_index("ix_tenant_quota_overrides_updated_by", table_name="tenant_quota_overrides")
    op.drop_index("ix_tenant_quota_overrides_is_active", table_name="tenant_quota_overrides")
    op.drop_index(
        "ix_tenant_quota_overrides_enforcement_mode",
        table_name="tenant_quota_overrides",
    )
    op.drop_index("ix_tenant_quota_overrides_quota_key", table_name="tenant_quota_overrides")
    op.drop_index("ix_tenant_quota_overrides_tenant_id", table_name="tenant_quota_overrides")
    op.drop_table("tenant_quota_overrides")

    op.drop_index("ix_tenant_subscriptions_tenant_start", table_name="tenant_subscriptions")
    op.drop_index("ix_tenant_subscriptions_tenant_status", table_name="tenant_subscriptions")
    op.drop_index("ix_tenant_subscriptions_tenant_plan", table_name="tenant_subscriptions")
    op.drop_index("ix_tenant_subscriptions_tenant_id_id", table_name="tenant_subscriptions")
    op.drop_index("ix_tenant_subscriptions_updated_at", table_name="tenant_subscriptions")
    op.drop_index("ix_tenant_subscriptions_created_at", table_name="tenant_subscriptions")
    op.drop_index("ix_tenant_subscriptions_created_by", table_name="tenant_subscriptions")
    op.drop_index("ix_tenant_subscriptions_auto_renew", table_name="tenant_subscriptions")
    op.drop_index("ix_tenant_subscriptions_end_at", table_name="tenant_subscriptions")
    op.drop_index("ix_tenant_subscriptions_start_at", table_name="tenant_subscriptions")
    op.drop_index("ix_tenant_subscriptions_status", table_name="tenant_subscriptions")
    op.drop_index("ix_tenant_subscriptions_plan_id", table_name="tenant_subscriptions")
    op.drop_index("ix_tenant_subscriptions_tenant_id", table_name="tenant_subscriptions")
    op.drop_table("tenant_subscriptions")

    op.drop_index("ix_billing_plan_quotas_tenant_key", table_name="billing_plan_quotas")
    op.drop_index("ix_billing_plan_quotas_tenant_plan", table_name="billing_plan_quotas")
    op.drop_index("ix_billing_plan_quotas_tenant_id_id", table_name="billing_plan_quotas")
    op.drop_index("ix_billing_plan_quotas_updated_at", table_name="billing_plan_quotas")
    op.drop_index("ix_billing_plan_quotas_created_at", table_name="billing_plan_quotas")
    op.drop_index("ix_billing_plan_quotas_enforcement_mode", table_name="billing_plan_quotas")
    op.drop_index("ix_billing_plan_quotas_quota_key", table_name="billing_plan_quotas")
    op.drop_index("ix_billing_plan_quotas_plan_id", table_name="billing_plan_quotas")
    op.drop_index("ix_billing_plan_quotas_tenant_id", table_name="billing_plan_quotas")
    op.drop_table("billing_plan_quotas")

    op.drop_index("ix_billing_plan_catalogs_tenant_active", table_name="billing_plan_catalogs")
    op.drop_index("ix_billing_plan_catalogs_tenant_cycle", table_name="billing_plan_catalogs")
    op.drop_index("ix_billing_plan_catalogs_tenant_plan_code", table_name="billing_plan_catalogs")
    op.drop_index("ix_billing_plan_catalogs_tenant_id_id", table_name="billing_plan_catalogs")
    op.drop_index("ix_billing_plan_catalogs_updated_at", table_name="billing_plan_catalogs")
    op.drop_index("ix_billing_plan_catalogs_created_at", table_name="billing_plan_catalogs")
    op.drop_index("ix_billing_plan_catalogs_created_by", table_name="billing_plan_catalogs")
    op.drop_index("ix_billing_plan_catalogs_is_active", table_name="billing_plan_catalogs")
    op.drop_index("ix_billing_plan_catalogs_currency", table_name="billing_plan_catalogs")
    op.drop_index("ix_billing_plan_catalogs_billing_cycle", table_name="billing_plan_catalogs")
    op.drop_index("ix_billing_plan_catalogs_display_name", table_name="billing_plan_catalogs")
    op.drop_index("ix_billing_plan_catalogs_plan_code", table_name="billing_plan_catalogs")
    op.drop_index("ix_billing_plan_catalogs_tenant_id", table_name="billing_plan_catalogs")
    op.drop_table("billing_plan_catalogs")
