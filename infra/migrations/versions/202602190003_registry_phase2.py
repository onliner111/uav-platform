"""registry phase2 tables

Revision ID: 202602190003
Revises: 202602190002
Create Date: 2026-02-19
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "202602190003"
down_revision = "202602190002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "drones",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("vendor", sa.String(), nullable=False),
        sa.Column("capabilities", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "name", name="uq_drones_tenant_name"),
    )
    op.create_index("ix_drones_tenant_id", "drones", ["tenant_id"])
    op.create_index("ix_drones_name", "drones", ["name"])
    op.create_index("ix_drones_created_at", "drones", ["created_at"])
    op.create_index("ix_drones_updated_at", "drones", ["updated_at"])

    op.create_table(
        "drone_credentials",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("drone_id", sa.String(), nullable=False),
        sa.Column("secret", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["drone_id"], ["drones.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("drone_id"),
    )
    op.create_index("ix_drone_credentials_tenant_id", "drone_credentials", ["tenant_id"])
    op.create_index("ix_drone_credentials_drone_id", "drone_credentials", ["drone_id"])
    op.create_index("ix_drone_credentials_created_at", "drone_credentials", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_drone_credentials_created_at", table_name="drone_credentials")
    op.drop_index("ix_drone_credentials_drone_id", table_name="drone_credentials")
    op.drop_index("ix_drone_credentials_tenant_id", table_name="drone_credentials")
    op.drop_table("drone_credentials")

    op.drop_index("ix_drones_updated_at", table_name="drones")
    op.drop_index("ix_drones_created_at", table_name="drones")
    op.drop_index("ix_drones_name", table_name="drones")
    op.drop_index("ix_drones_tenant_id", table_name="drones")
    op.drop_table("drones")

