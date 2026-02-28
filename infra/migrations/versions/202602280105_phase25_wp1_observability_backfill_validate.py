"""phase25 wp1 observability backfill validate

Revision ID: 202602280105
Revises: 202602280104
Create Date: 2026-02-28
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "202602280105"
down_revision = "202602280104"
branch_labels = None
depends_on = None


def _assert_zero(bind: sa.Connection, sql: str, error_message: str) -> None:
    rows = list(bind.execute(sa.text(sql)))
    if rows:
        raise RuntimeError(f"{error_message}. count={len(rows)}")


def upgrade() -> None:
    bind = op.get_bind()
    _assert_zero(
        bind,
        """
        SELECT id FROM observability_signals
        WHERE service_name = '' OR signal_name = ''
        """,
        "Phase25-WP1 validation failed: service_name/signal_name cannot be empty",
    )
    _assert_zero(
        bind,
        """
        SELECT id FROM observability_signals
        WHERE signal_type NOT IN ('LOG', 'METRIC', 'TRACE')
        """,
        "Phase25-WP1 validation failed: invalid signal_type",
    )
    _assert_zero(
        bind,
        """
        SELECT id FROM observability_signals
        WHERE level NOT IN ('DEBUG', 'INFO', 'WARN', 'ERROR')
        """,
        "Phase25-WP1 validation failed: invalid level",
    )


def downgrade() -> None:
    # Validation/backfill step only.
    pass
