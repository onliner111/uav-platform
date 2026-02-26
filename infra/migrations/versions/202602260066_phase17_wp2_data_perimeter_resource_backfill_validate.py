"""phase17 wp2 data perimeter resource backfill validate

Revision ID: 202602260066
Revises: 202602260065
Create Date: 2026-02-26
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "202602260066"
down_revision = "202602260065"
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
        SELECT id FROM data_access_policies
        WHERE json_typeof(resource_ids) <> 'array'
        """,
        "Phase17-WP2 validation failed: data_access_policies.resource_ids is not JSON array",
    )


def downgrade() -> None:
    # Validation-only step.
    pass
