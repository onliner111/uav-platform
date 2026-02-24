"""phase09 asset maintenance backfill validate

Revision ID: 202602240042
Revises: 202602240041
Create Date: 2026-02-24
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "202602240042"
down_revision = "202602240041"
branch_labels = None
depends_on = None


def _validate_workorder_status(bind: sa.Connection) -> None:
    rows = list(
        bind.execute(
            sa.text(
                """
                SELECT id
                FROM asset_maintenance_workorders
                WHERE status NOT IN ('OPEN', 'IN_PROGRESS', 'CLOSED', 'CANCELED')
                """
            )
        )
    )
    if rows:
        raise RuntimeError(
            "Phase09-WP3 validation failed: invalid workorder status "
            f"count={len(rows)}"
        )


def _validate_history_status(bind: sa.Connection, column: str) -> None:
    rows = list(
        bind.execute(
            sa.text(
                f"""
                SELECT id
                FROM asset_maintenance_histories
                WHERE {column} IS NOT NULL
                  AND {column} NOT IN ('OPEN', 'IN_PROGRESS', 'CLOSED', 'CANCELED')
                """
            )
        )
    )
    if rows:
        raise RuntimeError(
            f"Phase09-WP3 validation failed: invalid history {column} "
            f"count={len(rows)}"
        )


def _validate_priority_range(bind: sa.Connection) -> None:
    rows = list(
        bind.execute(
            sa.text(
                """
                SELECT id
                FROM asset_maintenance_workorders
                WHERE priority < 1 OR priority > 10
                """
            )
        )
    )
    if rows:
        raise RuntimeError(
            "Phase09-WP3 validation failed: invalid priority range "
            f"count={len(rows)}"
        )


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            UPDATE asset_maintenance_workorders
            SET status = 'OPEN'
            WHERE status IS NULL
            """
        )
    )
    _validate_workorder_status(bind)
    _validate_history_status(bind, "from_status")
    _validate_history_status(bind, "to_status")
    _validate_priority_range(bind)


def downgrade() -> None:
    # Validation-only step.
    pass
