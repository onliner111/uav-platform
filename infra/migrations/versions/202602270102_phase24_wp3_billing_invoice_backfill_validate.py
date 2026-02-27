"""phase24 wp3 billing invoice backfill validate

Revision ID: 202602270102
Revises: 202602270101
Create Date: 2026-02-27
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "202602270102"
down_revision = "202602270101"
branch_labels = None
depends_on = None


def _assert_zero(bind: sa.Connection, sql: str, error_message: str) -> None:
    rows = list(bind.execute(sa.text(sql)))
    if rows:
        raise RuntimeError(f"{error_message}. count={len(rows)}")


def upgrade() -> None:
    bind = op.get_bind()

    invoice_rows = list(
        bind.execute(
            sa.text(
                """
                SELECT id, adjustments_cents
                FROM billing_invoices
                """
            )
        ).mappings()
    )
    for row in invoice_rows:
        invoice_id = str(row["id"])
        adjustments = int(row["adjustments_cents"])
        sum_row = bind.execute(
            sa.text(
                """
                SELECT COALESCE(SUM(amount_cents), 0) AS subtotal
                FROM billing_invoice_lines
                WHERE invoice_id = :invoice_id
                """
            ),
            {"invoice_id": invoice_id},
        ).mappings().first()
        subtotal = int(sum_row["subtotal"] if sum_row is not None else 0)
        total = subtotal + adjustments
        bind.execute(
            sa.text(
                """
                UPDATE billing_invoices
                SET subtotal_cents = :subtotal_cents,
                    total_amount_cents = :total_amount_cents
                WHERE id = :id
                """
            ),
            {
                "id": invoice_id,
                "subtotal_cents": subtotal,
                "total_amount_cents": total,
            },
        )

    _assert_zero(
        bind,
        """
        SELECT id FROM billing_invoices WHERE period_end <= period_start
        """,
        "Phase24-WP3 validation failed: invoice period is invalid",
    )
    _assert_zero(
        bind,
        """
        SELECT id
        FROM billing_invoices
        WHERE status NOT IN ('DRAFT', 'ISSUED', 'CLOSED', 'VOID')
        """,
        "Phase24-WP3 validation failed: invoice status out of range",
    )
    _assert_zero(
        bind,
        """
        SELECT id FROM billing_invoice_lines WHERE amount_cents < 0
        """,
        "Phase24-WP3 validation failed: invoice line amount cannot be negative",
    )


def downgrade() -> None:
    # Validation/backfill step only.
    pass
