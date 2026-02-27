"""phase22 wp1 alert oncall backfill validate

Revision ID: 202602270087
Revises: 202602270086
Create Date: 2026-02-27
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "202602270087"
down_revision = "202602270086"
branch_labels = None
depends_on = None


def _validate_in_set(
    bind: sa.Connection,
    *,
    table: str,
    column: str,
    allowed_values: tuple[str, ...],
) -> None:
    in_values = ", ".join(f"'{value}'" for value in allowed_values)
    rows = list(
        bind.execute(
            sa.text(
                f"""
                SELECT id
                FROM {table}
                WHERE {column} NOT IN ({in_values})
                """
            )
        )
    )
    if rows:
        raise RuntimeError(
            f"Phase22-WP1 validation failed: {table}.{column} out of enum range. count={len(rows)}"
        )


def upgrade() -> None:
    bind = op.get_bind()
    invalid_windows = list(
        bind.execute(
            sa.text(
                """
                SELECT id
                FROM alert_oncall_shifts
                WHERE ends_at <= starts_at
                """
            )
        )
    )
    if invalid_windows:
        raise RuntimeError(
            "Phase22-WP1 validation failed: alert_oncall_shifts has invalid window. "
            f"count={len(invalid_windows)}"
        )

    invalid_policy_range = list(
        bind.execute(
            sa.text(
                """
                SELECT id
                FROM alert_escalation_policies
                WHERE ack_timeout_seconds < 30
                   OR repeat_threshold < 2
                   OR max_escalation_level < 1
                   OR escalation_target = ''
                """
            )
        )
    )
    if invalid_policy_range:
        raise RuntimeError(
            "Phase22-WP1 validation failed: alert_escalation_policies range check failed. "
            f"count={len(invalid_policy_range)}"
        )

    invalid_execution_range = list(
        bind.execute(
            sa.text(
                """
                SELECT id
                FROM alert_escalation_executions
                WHERE escalation_level < 1 OR to_target = ''
                """
            )
        )
    )
    if invalid_execution_range:
        raise RuntimeError(
            "Phase22-WP1 validation failed: alert_escalation_executions range check failed. "
            f"count={len(invalid_execution_range)}"
        )

    _validate_in_set(
        bind,
        table="alert_escalation_policies",
        column="priority_level",
        allowed_values=("P1", "P2", "P3"),
    )
    _validate_in_set(
        bind,
        table="alert_escalation_policies",
        column="escalation_channel",
        allowed_values=("IN_APP", "EMAIL", "SMS", "WEBHOOK"),
    )
    _validate_in_set(
        bind,
        table="alert_escalation_executions",
        column="reason",
        allowed_values=("ACK_TIMEOUT", "REPEAT_TRIGGER", "SHIFT_HANDOVER"),
    )
    _validate_in_set(
        bind,
        table="alert_escalation_executions",
        column="channel",
        allowed_values=("IN_APP", "EMAIL", "SMS", "WEBHOOK"),
    )
    _validate_in_set(
        bind,
        table="alert_handling_actions",
        column="action_type",
        allowed_values=("ACK", "DISPATCH", "ESCALATE", "VERIFY", "REVIEW", "CLOSE"),
    )


def downgrade() -> None:
    # Validation-only step.
    pass
