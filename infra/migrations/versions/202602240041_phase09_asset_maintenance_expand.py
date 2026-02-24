"""phase09 asset maintenance expand

Revision ID: 202602240041
Revises: 202602240040
Create Date: 2026-02-24
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "202602240041"
down_revision = "202602240040"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "asset_maintenance_workorders",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("asset_id", sa.String(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="OPEN"),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("assigned_to", sa.String(), nullable=True),
        sa.Column("close_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_by", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_asset_maintenance_workorders_tenant_id_id"),
    )
    op.create_index(
        "ix_asset_maintenance_workorders_tenant_id",
        "asset_maintenance_workorders",
        ["tenant_id"],
    )
    op.create_index("ix_asset_maintenance_workorders_asset_id", "asset_maintenance_workorders", ["asset_id"])
    op.create_index("ix_asset_maintenance_workorders_priority", "asset_maintenance_workorders", ["priority"])
    op.create_index("ix_asset_maintenance_workorders_status", "asset_maintenance_workorders", ["status"])
    op.create_index(
        "ix_asset_maintenance_workorders_created_by",
        "asset_maintenance_workorders",
        ["created_by"],
    )
    op.create_index(
        "ix_asset_maintenance_workorders_assigned_to",
        "asset_maintenance_workorders",
        ["assigned_to"],
    )
    op.create_index(
        "ix_asset_maintenance_workorders_created_at",
        "asset_maintenance_workorders",
        ["created_at"],
    )
    op.create_index(
        "ix_asset_maintenance_workorders_updated_at",
        "asset_maintenance_workorders",
        ["updated_at"],
    )
    op.create_index(
        "ix_asset_maintenance_workorders_closed_at",
        "asset_maintenance_workorders",
        ["closed_at"],
    )
    op.create_index(
        "ix_asset_maintenance_workorders_tenant_id_id",
        "asset_maintenance_workorders",
        ["tenant_id", "id"],
    )
    op.create_index(
        "ix_asset_maintenance_workorders_tenant_asset",
        "asset_maintenance_workorders",
        ["tenant_id", "asset_id"],
    )
    op.create_index(
        "ix_asset_maintenance_workorders_tenant_status",
        "asset_maintenance_workorders",
        ["tenant_id", "status"],
    )

    op.create_table(
        "asset_maintenance_histories",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("workorder_id", sa.String(), nullable=False),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("from_status", sa.String(length=30), nullable=True),
        sa.Column("to_status", sa.String(length=30), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("actor_id", sa.String(), nullable=True),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_asset_maintenance_histories_tenant_id_id"),
    )
    op.create_index("ix_asset_maintenance_histories_tenant_id", "asset_maintenance_histories", ["tenant_id"])
    op.create_index(
        "ix_asset_maintenance_histories_workorder_id",
        "asset_maintenance_histories",
        ["workorder_id"],
    )
    op.create_index("ix_asset_maintenance_histories_action", "asset_maintenance_histories", ["action"])
    op.create_index(
        "ix_asset_maintenance_histories_from_status",
        "asset_maintenance_histories",
        ["from_status"],
    )
    op.create_index(
        "ix_asset_maintenance_histories_to_status",
        "asset_maintenance_histories",
        ["to_status"],
    )
    op.create_index(
        "ix_asset_maintenance_histories_actor_id",
        "asset_maintenance_histories",
        ["actor_id"],
    )
    op.create_index(
        "ix_asset_maintenance_histories_created_at",
        "asset_maintenance_histories",
        ["created_at"],
    )
    op.create_index(
        "ix_asset_maintenance_histories_tenant_id_id",
        "asset_maintenance_histories",
        ["tenant_id", "id"],
    )
    op.create_index(
        "ix_asset_maintenance_histories_tenant_workorder",
        "asset_maintenance_histories",
        ["tenant_id", "workorder_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_asset_maintenance_histories_tenant_workorder", table_name="asset_maintenance_histories")
    op.drop_index("ix_asset_maintenance_histories_tenant_id_id", table_name="asset_maintenance_histories")
    op.drop_index("ix_asset_maintenance_histories_created_at", table_name="asset_maintenance_histories")
    op.drop_index("ix_asset_maintenance_histories_actor_id", table_name="asset_maintenance_histories")
    op.drop_index("ix_asset_maintenance_histories_to_status", table_name="asset_maintenance_histories")
    op.drop_index("ix_asset_maintenance_histories_from_status", table_name="asset_maintenance_histories")
    op.drop_index("ix_asset_maintenance_histories_action", table_name="asset_maintenance_histories")
    op.drop_index("ix_asset_maintenance_histories_workorder_id", table_name="asset_maintenance_histories")
    op.drop_index("ix_asset_maintenance_histories_tenant_id", table_name="asset_maintenance_histories")
    op.drop_table("asset_maintenance_histories")

    op.drop_index("ix_asset_maintenance_workorders_tenant_status", table_name="asset_maintenance_workorders")
    op.drop_index("ix_asset_maintenance_workorders_tenant_asset", table_name="asset_maintenance_workorders")
    op.drop_index("ix_asset_maintenance_workorders_tenant_id_id", table_name="asset_maintenance_workorders")
    op.drop_index("ix_asset_maintenance_workorders_closed_at", table_name="asset_maintenance_workorders")
    op.drop_index("ix_asset_maintenance_workorders_updated_at", table_name="asset_maintenance_workorders")
    op.drop_index("ix_asset_maintenance_workorders_created_at", table_name="asset_maintenance_workorders")
    op.drop_index("ix_asset_maintenance_workorders_assigned_to", table_name="asset_maintenance_workorders")
    op.drop_index("ix_asset_maintenance_workorders_created_by", table_name="asset_maintenance_workorders")
    op.drop_index("ix_asset_maintenance_workorders_status", table_name="asset_maintenance_workorders")
    op.drop_index("ix_asset_maintenance_workorders_priority", table_name="asset_maintenance_workorders")
    op.drop_index("ix_asset_maintenance_workorders_asset_id", table_name="asset_maintenance_workorders")
    op.drop_index("ix_asset_maintenance_workorders_tenant_id", table_name="asset_maintenance_workorders")
    op.drop_table("asset_maintenance_workorders")
