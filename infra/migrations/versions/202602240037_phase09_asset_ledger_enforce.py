"""phase09 asset ledger enforce

Revision ID: 202602240037
Revises: 202602240036
Create Date: 2026-02-24
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "202602240037"
down_revision = "202602240036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_foreign_key(
        "fk_assets_tenant_bound_drone",
        "assets",
        "drones",
        ["tenant_id", "bound_to_drone_id"],
        ["tenant_id", "id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_assets_tenant_bound_drone", "assets", type_="foreignkey")
