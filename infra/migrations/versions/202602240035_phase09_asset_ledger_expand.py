"""phase09 asset ledger expand

Revision ID: 202602240035
Revises: 202602240034
Create Date: 2026-02-24
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "202602240035"
down_revision = "202602240034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assets",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("asset_type", sa.String(length=30), nullable=False),
        sa.Column("asset_code", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("serial_number", sa.String(length=100), nullable=True),
        sa.Column("lifecycle_status", sa.String(length=30), nullable=False),
        sa.Column("bound_to_drone_id", sa.String(), nullable=True),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.Column("bound_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retired_reason", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_assets_tenant_id_id"),
        sa.UniqueConstraint("tenant_id", "asset_type", "asset_code", name="uq_assets_tenant_type_code"),
    )
    op.create_index("ix_assets_tenant_id", "assets", ["tenant_id"])
    op.create_index("ix_assets_asset_type", "assets", ["asset_type"])
    op.create_index("ix_assets_asset_code", "assets", ["asset_code"])
    op.create_index("ix_assets_name", "assets", ["name"])
    op.create_index("ix_assets_serial_number", "assets", ["serial_number"])
    op.create_index("ix_assets_lifecycle_status", "assets", ["lifecycle_status"])
    op.create_index("ix_assets_bound_to_drone_id", "assets", ["bound_to_drone_id"])
    op.create_index("ix_assets_bound_at", "assets", ["bound_at"])
    op.create_index("ix_assets_retired_at", "assets", ["retired_at"])
    op.create_index("ix_assets_created_at", "assets", ["created_at"])
    op.create_index("ix_assets_updated_at", "assets", ["updated_at"])
    op.create_index("ix_assets_tenant_id_id", "assets", ["tenant_id", "id"])
    op.create_index("ix_assets_tenant_type", "assets", ["tenant_id", "asset_type"])
    op.create_index("ix_assets_tenant_lifecycle", "assets", ["tenant_id", "lifecycle_status"])
    op.create_index("ix_assets_tenant_bound_drone", "assets", ["tenant_id", "bound_to_drone_id"])


def downgrade() -> None:
    op.drop_index("ix_assets_tenant_bound_drone", table_name="assets")
    op.drop_index("ix_assets_tenant_lifecycle", table_name="assets")
    op.drop_index("ix_assets_tenant_type", table_name="assets")
    op.drop_index("ix_assets_tenant_id_id", table_name="assets")
    op.drop_index("ix_assets_updated_at", table_name="assets")
    op.drop_index("ix_assets_created_at", table_name="assets")
    op.drop_index("ix_assets_retired_at", table_name="assets")
    op.drop_index("ix_assets_bound_at", table_name="assets")
    op.drop_index("ix_assets_bound_to_drone_id", table_name="assets")
    op.drop_index("ix_assets_lifecycle_status", table_name="assets")
    op.drop_index("ix_assets_serial_number", table_name="assets")
    op.drop_index("ix_assets_name", table_name="assets")
    op.drop_index("ix_assets_asset_code", table_name="assets")
    op.drop_index("ix_assets_asset_type", table_name="assets")
    op.drop_index("ix_assets_tenant_id", table_name="assets")
    op.drop_table("assets")
