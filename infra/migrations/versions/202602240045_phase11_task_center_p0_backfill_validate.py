"""phase11 task center p0 backfill validate

Revision ID: 202602240045
Revises: 202602240044
Create Date: 2026-02-25
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "202602240045"
down_revision = "202602240044"
branch_labels = None
depends_on = None


TASK_STATES = (
    "DRAFT",
    "APPROVAL_PENDING",
    "APPROVED",
    "REJECTED",
    "DISPATCHED",
    "IN_PROGRESS",
    "ACCEPTED",
    "ARCHIVED",
    "CANCELED",
)


def _validate_task_states(bind: sa.Connection) -> None:
    rows = list(
        bind.execute(
            sa.text(
                """
                SELECT id
                FROM task_center_tasks
                WHERE state NOT IN (
                    'DRAFT',
                    'APPROVAL_PENDING',
                    'APPROVED',
                    'REJECTED',
                    'DISPATCHED',
                    'IN_PROGRESS',
                    'ACCEPTED',
                    'ARCHIVED',
                    'CANCELED'
                )
                """
            )
        )
    )
    if rows:
        raise RuntimeError(
            "Phase11-P0 validation failed: invalid task state "
            f"count={len(rows)}"
        )


def _validate_task_priority_and_risk(bind: sa.Connection) -> None:
    invalid_priority = list(
        bind.execute(
            sa.text(
                """
                SELECT id
                FROM task_center_tasks
                WHERE priority < 1 OR priority > 10
                """
            )
        )
    )
    if invalid_priority:
        raise RuntimeError(
            "Phase11-P0 validation failed: invalid task priority "
            f"count={len(invalid_priority)}"
        )

    invalid_risk = list(
        bind.execute(
            sa.text(
                """
                SELECT id
                FROM task_center_tasks
                WHERE risk_level < 1 OR risk_level > 5
                """
            )
        )
    )
    if invalid_risk:
        raise RuntimeError(
            "Phase11-P0 validation failed: invalid task risk level "
            f"count={len(invalid_risk)}"
        )


def _validate_template_priority_and_risk(bind: sa.Connection) -> None:
    invalid_priority = list(
        bind.execute(
            sa.text(
                """
                SELECT id
                FROM task_templates
                WHERE default_priority < 1 OR default_priority > 10
                """
            )
        )
    )
    if invalid_priority:
        raise RuntimeError(
            "Phase11-P0 validation failed: invalid template default_priority "
            f"count={len(invalid_priority)}"
        )

    invalid_risk = list(
        bind.execute(
            sa.text(
                """
                SELECT id
                FROM task_templates
                WHERE default_risk_level < 1 OR default_risk_level > 5
                """
            )
        )
    )
    if invalid_risk:
        raise RuntimeError(
            "Phase11-P0 validation failed: invalid template default_risk_level "
            f"count={len(invalid_risk)}"
        )


def _validate_dispatch_mode(bind: sa.Connection) -> None:
    rows = list(
        bind.execute(
            sa.text(
                """
                SELECT id
                FROM task_center_tasks
                WHERE dispatch_mode IS NOT NULL
                  AND dispatch_mode NOT IN ('MANUAL', 'AUTO')
                """
            )
        )
    )
    if rows:
        raise RuntimeError(
            "Phase11-P0 validation failed: invalid dispatch_mode "
            f"count={len(rows)}"
        )


def _validate_history_states(bind: sa.Connection, column: str) -> None:
    rows = list(
        bind.execute(
            sa.text(
                f"""
                SELECT id
                FROM task_center_task_histories
                WHERE {column} IS NOT NULL
                  AND {column} NOT IN (
                    'DRAFT',
                    'APPROVAL_PENDING',
                    'APPROVED',
                    'REJECTED',
                    'DISPATCHED',
                    'IN_PROGRESS',
                    'ACCEPTED',
                    'ARCHIVED',
                    'CANCELED'
                  )
                """
            )
        )
    )
    if rows:
        raise RuntimeError(
            f"Phase11-P0 validation failed: invalid history {column} "
            f"count={len(rows)}"
        )


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            UPDATE task_center_tasks
            SET state = 'DRAFT'
            WHERE state IS NULL
            """
        )
    )
    _validate_task_states(bind)
    _validate_task_priority_and_risk(bind)
    _validate_template_priority_and_risk(bind)
    _validate_dispatch_mode(bind)
    _validate_history_states(bind, "from_state")
    _validate_history_states(bind, "to_state")


def downgrade() -> None:
    # Validation-only step.
    pass
