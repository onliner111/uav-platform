"""phase18 wp1 object storage backfill validate

Revision ID: 202602260072
Revises: 202602260071
Create Date: 2026-02-26
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "202602260072"
down_revision = "202602260071"
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
        SELECT id FROM raw_data_catalog_records
        WHERE (bucket IS NULL AND object_key IS NOT NULL)
           OR (bucket IS NOT NULL AND object_key IS NULL)
           OR (size_bytes IS NOT NULL AND size_bytes < 0)
        """,
        "Phase18-WP1 validation failed: raw_data_catalog_records invalid object storage fields",
    )
    _assert_zero(
        bind,
        """
        SELECT id FROM raw_upload_sessions
        WHERE status NOT IN ('INITIATED', 'UPLOADED', 'COMPLETED', 'EXPIRED')
           OR size_bytes <= 0
           OR json_typeof(meta) <> 'object'
           OR (completed_raw_id IS NOT NULL AND status <> 'COMPLETED')
        """,
        "Phase18-WP1 validation failed: raw_upload_sessions invalid rows",
    )


def downgrade() -> None:
    # Validation-only step.
    pass
