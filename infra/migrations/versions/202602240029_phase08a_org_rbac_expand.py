"""phase08a org rbac expand

Revision ID: 202602240029
Revises: 202602240028
Create Date: 2026-02-24
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "202602240029"
down_revision = "202602240028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "org_units",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("parent_id", sa.String(), nullable=True),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("path", sa.String(length=500), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_org_units_tenant_id_id"),
        sa.UniqueConstraint("tenant_id", "code", name="uq_org_units_tenant_code"),
    )
    op.create_index("ix_org_units_tenant_id", "org_units", ["tenant_id"])
    op.create_index("ix_org_units_name", "org_units", ["name"])
    op.create_index("ix_org_units_code", "org_units", ["code"])
    op.create_index("ix_org_units_parent_id", "org_units", ["parent_id"])
    op.create_index("ix_org_units_level", "org_units", ["level"])
    op.create_index("ix_org_units_is_active", "org_units", ["is_active"])
    op.create_index("ix_org_units_created_at", "org_units", ["created_at"])
    op.create_index("ix_org_units_updated_at", "org_units", ["updated_at"])
    op.create_index(
        "ix_org_units_tenant_id_id",
        "org_units",
        ["tenant_id", "id"],
    )
    op.create_index(
        "ix_org_units_tenant_parent_id",
        "org_units",
        ["tenant_id", "parent_id"],
    )

    op.create_table(
        "user_org_memberships",
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("org_unit_id", sa.String(), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("tenant_id", "user_id", "org_unit_id"),
    )
    op.create_index(
        "ix_user_org_memberships_tenant_user",
        "user_org_memberships",
        ["tenant_id", "user_id"],
    )
    op.create_index(
        "ix_user_org_memberships_tenant_org",
        "user_org_memberships",
        ["tenant_id", "org_unit_id"],
    )
    op.create_index(
        "ix_user_org_memberships_is_primary",
        "user_org_memberships",
        ["is_primary"],
    )
    op.create_index(
        "ix_user_org_memberships_created_at",
        "user_org_memberships",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_user_org_memberships_created_at", table_name="user_org_memberships")
    op.drop_index("ix_user_org_memberships_is_primary", table_name="user_org_memberships")
    op.drop_index("ix_user_org_memberships_tenant_org", table_name="user_org_memberships")
    op.drop_index("ix_user_org_memberships_tenant_user", table_name="user_org_memberships")
    op.drop_table("user_org_memberships")

    op.drop_index("ix_org_units_tenant_parent_id", table_name="org_units")
    op.drop_index("ix_org_units_tenant_id_id", table_name="org_units")
    op.drop_index("ix_org_units_updated_at", table_name="org_units")
    op.drop_index("ix_org_units_created_at", table_name="org_units")
    op.drop_index("ix_org_units_is_active", table_name="org_units")
    op.drop_index("ix_org_units_level", table_name="org_units")
    op.drop_index("ix_org_units_parent_id", table_name="org_units")
    op.drop_index("ix_org_units_code", table_name="org_units")
    op.drop_index("ix_org_units_name", table_name="org_units")
    op.drop_index("ix_org_units_tenant_id", table_name="org_units")
    op.drop_table("org_units")

