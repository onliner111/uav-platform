"""phase09 asset availability backfill validate

Revision ID: 202602240039
Revises: 202602240038
Create Date: 2026-02-24
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "202602240039"
down_revision = "202602240038"
branch_labels = None
depends_on = None


def _validate_availability_status(bind: sa.Connection) -> None:
    rows = list(
        bind.execute(
            sa.text(
                """
                SELECT id
                FROM assets
                WHERE availability_status NOT IN (
                    'AVAILABLE', 'RESERVED', 'IN_USE', 'MAINTENANCE', 'UNAVAILABLE'
                )
                """
            )
        )
    )
    if rows:
        raise RuntimeError(
            "Phase09-WP2 validation failed: invalid availability_status detected "
            f"count={len(rows)}"
        )


def _validate_health_status(bind: sa.Connection) -> None:
    rows = list(
        bind.execute(
            sa.text(
                """
                SELECT id
                FROM assets
                WHERE health_status NOT IN ('UNKNOWN', 'HEALTHY', 'DEGRADED', 'CRITICAL')
                """
            )
        )
    )
    if rows:
        raise RuntimeError(
            "Phase09-WP2 validation failed: invalid health_status detected "
            f"count={len(rows)}"
        )


def _validate_health_score(bind: sa.Connection) -> None:
    rows = list(
        bind.execute(
            sa.text(
                """
                SELECT id
                FROM assets
                WHERE health_score IS NOT NULL
                  AND (health_score < 0 OR health_score > 100)
                """
            )
        )
    )
    if rows:
        raise RuntimeError(
            "Phase09-WP2 validation failed: invalid health_score detected "
            f"count={len(rows)}"
        )


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            UPDATE assets
            SET availability_status = 'AVAILABLE'
            WHERE availability_status IS NULL
            """
        )
    )
    bind.execute(
        sa.text(
            """
            UPDATE assets
            SET health_status = 'UNKNOWN'
            WHERE health_status IS NULL
            """
        )
    )
    _validate_availability_status(bind)
    _validate_health_status(bind)
    _validate_health_score(bind)


def downgrade() -> None:
    # Validation-only step.
    pass
