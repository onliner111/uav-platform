"""phase18 wp5 storage tier region backfill validate

Revision ID: 202602260081
Revises: 202602260080
Create Date: 2026-02-26
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "202602260081"
down_revision = "202602260080"
branch_labels = None
depends_on = None


def _assert_zero(bind: sa.engine.Connection, sql: str, message: str) -> None:
    rows = list(bind.execute(sa.text(sql)))
    if rows:
        raise RuntimeError(f"{message}. count={len(rows)}")


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            UPDATE raw_data_catalog_records
            SET access_tier = 'HOT'
            WHERE access_tier IS NULL
            """
        )
    )
    _assert_zero(
        bind,
        """
        SELECT id FROM raw_data_catalog_records
        WHERE access_tier NOT IN ('HOT', 'WARM', 'COLD')
           OR (storage_region IS NOT NULL AND storage_region = '')
        """,
        "Phase18-WP5 validation failed: raw_data_catalog_records invalid storage tier/region rows",
    )
    _assert_zero(
        bind,
        """
        SELECT id FROM raw_upload_sessions
        WHERE storage_region IS NULL OR storage_region = ''
        """,
        "Phase18-WP5 validation failed: raw_upload_sessions invalid storage_region rows",
    )


def downgrade() -> None:
    # Validation-only step.
    pass
