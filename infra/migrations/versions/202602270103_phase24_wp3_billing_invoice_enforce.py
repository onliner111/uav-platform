"""phase24 wp3 billing invoice enforce

Revision ID: 202602270103
Revises: 202602270102
Create Date: 2026-02-27
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "202602270103"
down_revision = "202602270102"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_billing_invoices_period_window",
        "billing_invoices",
        "period_end > period_start",
    )
    op.create_check_constraint(
        "ck_billing_invoices_status",
        "billing_invoices",
        "status IN ('DRAFT', 'ISSUED', 'CLOSED', 'VOID')",
    )
    op.create_check_constraint(
        "ck_billing_invoices_currency_not_empty",
        "billing_invoices",
        "currency <> ''",
    )
    op.create_check_constraint(
        "ck_billing_invoice_lines_type",
        "billing_invoice_lines",
        "line_type IN ('PLAN_BASE', 'USAGE', 'ADJUSTMENT')",
    )
    op.create_check_constraint(
        "ck_billing_invoice_lines_quantity_non_negative",
        "billing_invoice_lines",
        "quantity >= 0",
    )
    op.create_check_constraint(
        "ck_billing_invoice_lines_amount_non_negative",
        "billing_invoice_lines",
        "amount_cents >= 0",
    )

    op.create_foreign_key(
        "fk_billing_invoices_tenant_subscription",
        "billing_invoices",
        "tenant_subscriptions",
        ["tenant_id", "subscription_id"],
        ["tenant_id", "id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_billing_invoices_tenant_plan",
        "billing_invoices",
        "billing_plan_catalogs",
        ["tenant_id", "plan_id"],
        ["tenant_id", "id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_billing_invoice_lines_tenant_invoice",
        "billing_invoice_lines",
        "billing_invoices",
        ["tenant_id", "invoice_id"],
        ["tenant_id", "id"],
        ondelete="CASCADE",
    )

    op.create_index(
        "uq_billing_invoices_tenant_period_issued_closed",
        "billing_invoices",
        ["tenant_id", "period_start", "period_end"],
        unique=True,
        postgresql_where=sa.text("status IN ('ISSUED', 'CLOSED')"),
        sqlite_where=sa.text("status IN ('ISSUED', 'CLOSED')"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_billing_invoices_tenant_period_issued_closed",
        table_name="billing_invoices",
    )

    op.drop_constraint(
        "fk_billing_invoice_lines_tenant_invoice",
        "billing_invoice_lines",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_billing_invoices_tenant_plan",
        "billing_invoices",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_billing_invoices_tenant_subscription",
        "billing_invoices",
        type_="foreignkey",
    )

    op.drop_constraint(
        "ck_billing_invoice_lines_amount_non_negative",
        "billing_invoice_lines",
        type_="check",
    )
    op.drop_constraint(
        "ck_billing_invoice_lines_quantity_non_negative",
        "billing_invoice_lines",
        type_="check",
    )
    op.drop_constraint(
        "ck_billing_invoice_lines_type",
        "billing_invoice_lines",
        type_="check",
    )
    op.drop_constraint(
        "ck_billing_invoices_currency_not_empty",
        "billing_invoices",
        type_="check",
    )
    op.drop_constraint(
        "ck_billing_invoices_status",
        "billing_invoices",
        type_="check",
    )
    op.drop_constraint(
        "ck_billing_invoices_period_window",
        "billing_invoices",
        type_="check",
    )
