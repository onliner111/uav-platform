"""phase13 alert handling chain backfill validate

Revision ID: 202602250054
Revises: 202602250053
Create Date: 2026-02-25
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "202602250054"
down_revision = "202602250053"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    rows = list(
        bind.execute(
            sa.text(
                """
                SELECT id
                FROM alert_handling_actions
                WHERE action_type NOT IN ('ACK', 'DISPATCH', 'VERIFY', 'REVIEW', 'CLOSE')
                """
            )
        )
    )
    if rows:
        raise RuntimeError(
            "Phase13-WP3 validation failed: alert_handling_actions.action_type out of enum range. "
            f"count={len(rows)}"
        )


def downgrade() -> None:
    # Validation-only step.
    pass
