"""phase24 wp3 billing invoice expand

Revision ID: 202602270101
Revises: 202602270100
Create Date: 2026-02-27
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "202602270101"
down_revision = "202602270100"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "billing_invoices",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("subscription_id", sa.String(), nullable=False),
        sa.Column("plan_id", sa.String(), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("currency", sa.String(length=20), nullable=False, server_default="CNY"),
        sa.Column("subtotal_cents", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("adjustments_cents", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("total_amount_cents", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_billing_invoices_tenant_id_id"),
    )
    op.create_index("ix_billing_invoices_tenant_id", "billing_invoices", ["tenant_id"])
    op.create_index("ix_billing_invoices_subscription_id", "billing_invoices", ["subscription_id"])
    op.create_index("ix_billing_invoices_plan_id", "billing_invoices", ["plan_id"])
    op.create_index("ix_billing_invoices_period_start", "billing_invoices", ["period_start"])
    op.create_index("ix_billing_invoices_period_end", "billing_invoices", ["period_end"])
    op.create_index("ix_billing_invoices_status", "billing_invoices", ["status"])
    op.create_index("ix_billing_invoices_currency", "billing_invoices", ["currency"])
    op.create_index("ix_billing_invoices_issued_at", "billing_invoices", ["issued_at"])
    op.create_index("ix_billing_invoices_closed_at", "billing_invoices", ["closed_at"])
    op.create_index("ix_billing_invoices_voided_at", "billing_invoices", ["voided_at"])
    op.create_index("ix_billing_invoices_created_by", "billing_invoices", ["created_by"])
    op.create_index("ix_billing_invoices_created_at", "billing_invoices", ["created_at"])
    op.create_index("ix_billing_invoices_updated_at", "billing_invoices", ["updated_at"])
    op.create_index("ix_billing_invoices_tenant_id_id", "billing_invoices", ["tenant_id", "id"])
    op.create_index(
        "ix_billing_invoices_tenant_period",
        "billing_invoices",
        ["tenant_id", "period_start", "period_end"],
    )
    op.create_index(
        "ix_billing_invoices_tenant_status",
        "billing_invoices",
        ["tenant_id", "status"],
    )

    op.create_table(
        "billing_invoice_lines",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("invoice_id", sa.String(), nullable=False),
        sa.Column("line_type", sa.String(length=50), nullable=False),
        sa.Column("meter_key", sa.String(length=120), nullable=True),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("unit_price_cents", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("amount_cents", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_billing_invoice_lines_tenant_id_id"),
    )
    op.create_index("ix_billing_invoice_lines_tenant_id", "billing_invoice_lines", ["tenant_id"])
    op.create_index("ix_billing_invoice_lines_invoice_id", "billing_invoice_lines", ["invoice_id"])
    op.create_index("ix_billing_invoice_lines_line_type", "billing_invoice_lines", ["line_type"])
    op.create_index("ix_billing_invoice_lines_meter_key", "billing_invoice_lines", ["meter_key"])
    op.create_index("ix_billing_invoice_lines_created_at", "billing_invoice_lines", ["created_at"])
    op.create_index(
        "ix_billing_invoice_lines_tenant_id_id",
        "billing_invoice_lines",
        ["tenant_id", "id"],
    )
    op.create_index(
        "ix_billing_invoice_lines_tenant_invoice",
        "billing_invoice_lines",
        ["tenant_id", "invoice_id"],
    )
    op.create_index(
        "ix_billing_invoice_lines_tenant_type",
        "billing_invoice_lines",
        ["tenant_id", "line_type"],
    )


def downgrade() -> None:
    op.drop_index("ix_billing_invoice_lines_tenant_type", table_name="billing_invoice_lines")
    op.drop_index("ix_billing_invoice_lines_tenant_invoice", table_name="billing_invoice_lines")
    op.drop_index("ix_billing_invoice_lines_tenant_id_id", table_name="billing_invoice_lines")
    op.drop_index("ix_billing_invoice_lines_created_at", table_name="billing_invoice_lines")
    op.drop_index("ix_billing_invoice_lines_meter_key", table_name="billing_invoice_lines")
    op.drop_index("ix_billing_invoice_lines_line_type", table_name="billing_invoice_lines")
    op.drop_index("ix_billing_invoice_lines_invoice_id", table_name="billing_invoice_lines")
    op.drop_index("ix_billing_invoice_lines_tenant_id", table_name="billing_invoice_lines")
    op.drop_table("billing_invoice_lines")

    op.drop_index("ix_billing_invoices_tenant_status", table_name="billing_invoices")
    op.drop_index("ix_billing_invoices_tenant_period", table_name="billing_invoices")
    op.drop_index("ix_billing_invoices_tenant_id_id", table_name="billing_invoices")
    op.drop_index("ix_billing_invoices_updated_at", table_name="billing_invoices")
    op.drop_index("ix_billing_invoices_created_at", table_name="billing_invoices")
    op.drop_index("ix_billing_invoices_created_by", table_name="billing_invoices")
    op.drop_index("ix_billing_invoices_voided_at", table_name="billing_invoices")
    op.drop_index("ix_billing_invoices_closed_at", table_name="billing_invoices")
    op.drop_index("ix_billing_invoices_issued_at", table_name="billing_invoices")
    op.drop_index("ix_billing_invoices_currency", table_name="billing_invoices")
    op.drop_index("ix_billing_invoices_status", table_name="billing_invoices")
    op.drop_index("ix_billing_invoices_period_end", table_name="billing_invoices")
    op.drop_index("ix_billing_invoices_period_start", table_name="billing_invoices")
    op.drop_index("ix_billing_invoices_plan_id", table_name="billing_invoices")
    op.drop_index("ix_billing_invoices_subscription_id", table_name="billing_invoices")
    op.drop_index("ix_billing_invoices_tenant_id", table_name="billing_invoices")
    op.drop_table("billing_invoices")
