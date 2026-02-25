"""phase12 airspace compliance backfill validate

Revision ID: 202602250048
Revises: 202602250047
Create Date: 2026-02-25
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "202602250048"
down_revision = "202602250047"
branch_labels = None
depends_on = None


ZONE_TYPES = ("NO_FLY", "ALT_LIMIT", "SENSITIVE")
CHECKLIST_STATUSES = ("PENDING", "IN_PROGRESS", "COMPLETED", "WAIVED")
REASON_CODES = (
    "AIRSPACE_NO_FLY",
    "AIRSPACE_ALT_LIMIT_EXCEEDED",
    "AIRSPACE_SENSITIVE_RESTRICTED",
    "PREFLIGHT_CHECKLIST_REQUIRED",
    "PREFLIGHT_CHECKLIST_INCOMPLETE",
    "COMMAND_GEOFENCE_BLOCKED",
    "COMMAND_ALTITUDE_BLOCKED",
    "COMMAND_SENSITIVE_RESTRICTED",
)


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
            f"Phase12 validation failed: {table}.{column} out of enum range. count={len(rows)}"
        )


def upgrade() -> None:
    bind = op.get_bind()

    bind.execute(
        sa.text(
            """
            UPDATE command_requests
            SET compliance_detail = '{}'
            WHERE compliance_detail IS NULL
            """
        )
    )

    _validate_in_set(
        bind,
        table="airspace_zones",
        column="zone_type",
        allowed_values=ZONE_TYPES,
    )
    _validate_in_set(
        bind,
        table="mission_preflight_checklists",
        column="status",
        allowed_values=CHECKLIST_STATUSES,
    )
    _validate_in_set(
        bind,
        table="command_requests",
        column="compliance_reason_code",
        allowed_values=REASON_CODES,
        allow_null=True,
    )


def downgrade() -> None:
    # Validation-only step.
    pass
