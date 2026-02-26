"""phase17 wp2 data perimeter resource expand

Revision ID: 202602260065
Revises: 202602260064
Create Date: 2026-02-26
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "202602260065"
down_revision = "202602260064"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "data_access_policies",
        sa.Column(
            "resource_ids",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::json"),
        ),
    )


def downgrade() -> None:
    op.drop_column("data_access_policies", "resource_ids")
