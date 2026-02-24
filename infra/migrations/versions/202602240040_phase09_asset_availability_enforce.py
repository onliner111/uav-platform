"""phase09 asset availability enforce

Revision ID: 202602240040
Revises: 202602240039
Create Date: 2026-02-24
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "202602240040"
down_revision = "202602240039"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_assets_health_score_range",
        "assets",
        "(health_score IS NULL) OR (health_score >= 0 AND health_score <= 100)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_assets_health_score_range", "assets", type_="check")
