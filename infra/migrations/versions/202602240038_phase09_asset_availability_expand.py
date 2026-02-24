"""phase09 asset availability expand

Revision ID: 202602240038
Revises: 202602240037
Create Date: 2026-02-24
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "202602240038"
down_revision = "202602240037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "assets",
        sa.Column(
            "availability_status",
            sa.String(length=30),
            nullable=False,
            server_default="AVAILABLE",
        ),
    )
    op.add_column(
        "assets",
        sa.Column(
            "health_status",
            sa.String(length=30),
            nullable=False,
            server_default="UNKNOWN",
        ),
    )
    op.add_column("assets", sa.Column("health_score", sa.Integer(), nullable=True))
    op.add_column("assets", sa.Column("region_code", sa.String(length=100), nullable=True))
    op.add_column("assets", sa.Column("last_health_at", sa.DateTime(timezone=True), nullable=True))

    op.create_index("ix_assets_availability_status", "assets", ["availability_status"])
    op.create_index("ix_assets_health_status", "assets", ["health_status"])
    op.create_index("ix_assets_health_score", "assets", ["health_score"])
    op.create_index("ix_assets_region_code", "assets", ["region_code"])
    op.create_index("ix_assets_last_health_at", "assets", ["last_health_at"])
    op.create_index("ix_assets_tenant_availability", "assets", ["tenant_id", "availability_status"])
    op.create_index("ix_assets_tenant_health", "assets", ["tenant_id", "health_status"])
    op.create_index("ix_assets_tenant_region", "assets", ["tenant_id", "region_code"])


def downgrade() -> None:
    op.drop_index("ix_assets_tenant_region", table_name="assets")
    op.drop_index("ix_assets_tenant_health", table_name="assets")
    op.drop_index("ix_assets_tenant_availability", table_name="assets")
    op.drop_index("ix_assets_last_health_at", table_name="assets")
    op.drop_index("ix_assets_region_code", table_name="assets")
    op.drop_index("ix_assets_health_score", table_name="assets")
    op.drop_index("ix_assets_health_status", table_name="assets")
    op.drop_index("ix_assets_availability_status", table_name="assets")
    op.drop_column("assets", "last_health_at")
    op.drop_column("assets", "region_code")
    op.drop_column("assets", "health_score")
    op.drop_column("assets", "health_status")
    op.drop_column("assets", "availability_status")
