"""phase17 p2 policy inheritance expand

Revision ID: 202602260068
Revises: 202602260067
Create Date: 2026-02-26
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "202602260068"
down_revision = "202602260067"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "data_access_policies",
        sa.Column(
            "denied_org_unit_ids",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::json"),
        ),
    )
    op.add_column(
        "data_access_policies",
        sa.Column(
            "denied_project_codes",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::json"),
        ),
    )
    op.add_column(
        "data_access_policies",
        sa.Column(
            "denied_area_codes",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::json"),
        ),
    )
    op.add_column(
        "data_access_policies",
        sa.Column(
            "denied_task_ids",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::json"),
        ),
    )
    op.add_column(
        "data_access_policies",
        sa.Column(
            "denied_resource_ids",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::json"),
        ),
    )

    op.create_table(
        "role_data_access_policies",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("role_id", sa.String(), nullable=False),
        sa.Column("scope_mode", sa.String(length=20), nullable=False, server_default="SCOPED"),
        sa.Column("org_unit_ids", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("project_codes", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("area_codes", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("task_ids", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("resource_ids", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "role_id"],
            ["roles.tenant_id", "roles.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "role_id", name="uq_role_data_access_policies_tenant_role"),
    )
    op.create_index("ix_role_data_access_policies_tenant_id", "role_data_access_policies", ["tenant_id"])
    op.create_index("ix_role_data_access_policies_role_id", "role_data_access_policies", ["role_id"])
    op.create_index(
        "ix_role_data_access_policies_tenant_role",
        "role_data_access_policies",
        ["tenant_id", "role_id"],
    )
    op.create_index(
        "ix_role_data_access_policies_scope_mode",
        "role_data_access_policies",
        ["scope_mode"],
    )
    op.create_index(
        "ix_role_data_access_policies_created_at",
        "role_data_access_policies",
        ["created_at"],
    )
    op.create_index(
        "ix_role_data_access_policies_updated_at",
        "role_data_access_policies",
        ["updated_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_role_data_access_policies_updated_at", table_name="role_data_access_policies")
    op.drop_index("ix_role_data_access_policies_created_at", table_name="role_data_access_policies")
    op.drop_index("ix_role_data_access_policies_scope_mode", table_name="role_data_access_policies")
    op.drop_index("ix_role_data_access_policies_tenant_role", table_name="role_data_access_policies")
    op.drop_index("ix_role_data_access_policies_role_id", table_name="role_data_access_policies")
    op.drop_index("ix_role_data_access_policies_tenant_id", table_name="role_data_access_policies")
    op.drop_table("role_data_access_policies")

    op.drop_column("data_access_policies", "denied_resource_ids")
    op.drop_column("data_access_policies", "denied_task_ids")
    op.drop_column("data_access_policies", "denied_area_codes")
    op.drop_column("data_access_policies", "denied_project_codes")
    op.drop_column("data_access_policies", "denied_org_unit_ids")
