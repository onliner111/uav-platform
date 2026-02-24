"""phase09 asset maintenance enforce

Revision ID: 202602240043
Revises: 202602240042
Create Date: 2026-02-24
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "202602240043"
down_revision = "202602240042"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_asset_maintenance_workorders_priority_range",
        "asset_maintenance_workorders",
        "priority >= 1 AND priority <= 10",
    )
    op.create_foreign_key(
        "fk_asset_maintenance_workorders_tenant_asset",
        "asset_maintenance_workorders",
        "assets",
        ["tenant_id", "asset_id"],
        ["tenant_id", "id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_asset_maintenance_histories_tenant_workorder",
        "asset_maintenance_histories",
        "asset_maintenance_workorders",
        ["tenant_id", "workorder_id"],
        ["tenant_id", "id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_asset_maintenance_histories_tenant_workorder",
        "asset_maintenance_histories",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_asset_maintenance_workorders_tenant_asset",
        "asset_maintenance_workorders",
        type_="foreignkey",
    )
    op.drop_constraint(
        "ck_asset_maintenance_workorders_priority_range",
        "asset_maintenance_workorders",
        type_="check",
    )
