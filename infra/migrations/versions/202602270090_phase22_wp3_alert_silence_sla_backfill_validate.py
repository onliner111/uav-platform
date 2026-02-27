"""phase22 wp3 alert silence sla backfill validate

Revision ID: 202602270090
Revises: 202602270089
Create Date: 2026-02-27
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "202602270090"
down_revision = "202602270089"
branch_labels = None
depends_on = None


def _validate_in_set(
    bind: sa.Connection,
    *,
    table: str,
    column: str,
    allowed_values: tuple[str, ...],
    allow_null: bool = False,
) -> None:
    null_sql = "" if not allow_null else f"{column} IS NOT NULL AND "
    in_values = ", ".join(f"'{value}'" for value in allowed_values)
    rows = list(
        bind.execute(
            sa.text(
                f"""
                SELECT id
                FROM {table}
                WHERE {null_sql}{column} NOT IN ({in_values})
                """
            )
        )
    )
    if rows:
        raise RuntimeError(
            f"Phase22-WP3 validation failed: {table}.{column} out of enum range. count={len(rows)}"
        )


def upgrade() -> None:
    bind = op.get_bind()
    invalid_silence_window = list(
        bind.execute(
            sa.text(
                """
                SELECT id
                FROM alert_silence_rules
                WHERE starts_at IS NOT NULL
                  AND ends_at IS NOT NULL
                  AND ends_at <= starts_at
                """
            )
        )
    )
    if invalid_silence_window:
        raise RuntimeError(
            "Phase22-WP3 validation failed: alert_silence_rules window invalid. "
            f"count={len(invalid_silence_window)}"
        )

    invalid_aggregation_window = list(
        bind.execute(
            sa.text(
                """
                SELECT id
                FROM alert_aggregation_rules
                WHERE window_seconds < 10
                """
            )
        )
    )
    if invalid_aggregation_window:
        raise RuntimeError(
            "Phase22-WP3 validation failed: alert_aggregation_rules window_seconds invalid. "
            f"count={len(invalid_aggregation_window)}"
        )

    _validate_in_set(
        bind,
        table="alert_silence_rules",
        column="alert_type",
        allowed_values=("LOW_BATTERY", "LINK_LOSS", "GEOFENCE_BREACH"),
        allow_null=True,
    )
    _validate_in_set(
        bind,
        table="alert_aggregation_rules",
        column="alert_type",
        allowed_values=("LOW_BATTERY", "LINK_LOSS", "GEOFENCE_BREACH"),
        allow_null=True,
    )


def downgrade() -> None:
    # Validation-only step.
    pass
