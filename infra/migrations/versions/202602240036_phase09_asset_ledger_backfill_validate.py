"""phase09 asset ledger backfill validate

Revision ID: 202602240036
Revises: 202602240035
Create Date: 2026-02-24
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "202602240036"
down_revision = "202602240035"
branch_labels = None
depends_on = None


def _validate_tenant_scoped_asset_code(bind: sa.Connection) -> None:
    rows = list(
        bind.execute(
            sa.text(
                """
                SELECT tenant_id, asset_type, asset_code, COUNT(*) AS c
                FROM assets
                GROUP BY tenant_id, asset_type, asset_code
                HAVING COUNT(*) > 1
                """
            )
        )
    )
    if rows:
        raise RuntimeError(
            "Phase09 validation failed: duplicated asset_code under same tenant/type "
            f"count={len(rows)}"
        )


def _validate_lifecycle_status(bind: sa.Connection) -> None:
    rows = list(
        bind.execute(
            sa.text(
                """
                SELECT id
                FROM assets
                WHERE lifecycle_status NOT IN ('REGISTERED', 'BOUND', 'RETIRED')
                """
            )
        )
    )
    if rows:
        raise RuntimeError(
            "Phase09 validation failed: invalid lifecycle_status detected "
            f"count={len(rows)}"
        )


def upgrade() -> None:
    bind = op.get_bind()
    _validate_tenant_scoped_asset_code(bind)
    _validate_lifecycle_status(bind)


def downgrade() -> None:
    # Validation-only step.
    pass
