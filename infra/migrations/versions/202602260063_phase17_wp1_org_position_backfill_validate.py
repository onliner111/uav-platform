"""phase17 wp1 org position backfill validate

Revision ID: 202602260063
Revises: 202602260062
Create Date: 2026-02-26
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "202602260063"
down_revision = "202602260062"
branch_labels = None
depends_on = None


def _assert_zero(bind: sa.engine.Connection, sql: str, message: str) -> None:
    rows = list(bind.execute(sa.text(sql)))
    if rows:
        raise RuntimeError(f"{message}. count={len(rows)}")


def upgrade() -> None:
    bind = op.get_bind()
    _assert_zero(
        bind,
        """
        SELECT id FROM org_units
        WHERE unit_type NOT IN ('ORGANIZATION', 'DEPARTMENT')
        """,
        "Phase17-WP1 validation failed: org_units.unit_type out of enum range",
    )


def downgrade() -> None:
    # Validation-only step.
    pass
