"""phase18 wp3 report template export backfill validate

Revision ID: 202602260078
Revises: 202602260077
Create Date: 2026-02-26
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "202602260078"
down_revision = "202602260077"
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
        SELECT id FROM outcome_report_templates
        WHERE format_default NOT IN ('PDF', 'WORD')
           OR name = ''
           OR title_template IS NULL
           OR body_template IS NULL
        """,
        "Phase18-WP3 validation failed: outcome_report_templates invalid rows",
    )
    _assert_zero(
        bind,
        """
        SELECT id FROM outcome_report_exports
        WHERE report_format NOT IN ('PDF', 'WORD')
           OR status NOT IN ('RUNNING', 'SUCCEEDED', 'FAILED')
           OR json_typeof(detail) <> 'object'
        """,
        "Phase18-WP3 validation failed: outcome_report_exports invalid rows",
    )


def downgrade() -> None:
    # Validation-only step.
    pass
