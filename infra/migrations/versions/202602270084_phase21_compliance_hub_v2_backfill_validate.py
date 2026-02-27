"""phase21 compliance hub v2 backfill validate

Revision ID: 202602270084
Revises: 202602270083
Create Date: 2026-02-27
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "202602270084"
down_revision = "202602270083"
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
            f"Phase21 validation failed: {table}.{column} out of enum range. count={len(rows)}"
        )


def upgrade() -> None:
    bind = op.get_bind()

    bind.execute(
        sa.text(
            """
            UPDATE airspace_zones
            SET policy_layer = 'TENANT'
            WHERE policy_layer IS NULL
            """
        )
    )
    bind.execute(
        sa.text(
            """
            UPDATE airspace_zones
            SET policy_effect = 'DENY'
            WHERE policy_effect IS NULL
            """
        )
    )
    bind.execute(
        sa.text(
            """
            UPDATE preflight_checklist_templates
            SET template_version = 'v1'
            WHERE template_version IS NULL OR template_version = ''
            """
        )
    )
    bind.execute(
        sa.text(
            """
            UPDATE preflight_checklist_templates
            SET evidence_requirements = '{}'
            WHERE evidence_requirements IS NULL
            """
        )
    )

    _validate_in_set(
        bind,
        table="airspace_zones",
        column="policy_layer",
        allowed_values=("PLATFORM_DEFAULT", "TENANT", "ORG_UNIT"),
    )
    _validate_in_set(
        bind,
        table="airspace_zones",
        column="policy_effect",
        allowed_values=("ALLOW", "DENY"),
    )
    _validate_in_set(
        bind,
        table="compliance_approval_flow_instances",
        column="status",
        allowed_values=("PENDING", "APPROVED", "REJECTED"),
    )
    _validate_in_set(
        bind,
        table="compliance_decision_records",
        column="decision",
        allowed_values=("ALLOW", "DENY", "APPROVE", "REJECT"),
    )


def downgrade() -> None:
    # Validation-only step.
    pass
