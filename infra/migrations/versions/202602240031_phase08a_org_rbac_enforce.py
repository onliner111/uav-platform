"""phase08a org rbac enforce

Revision ID: 202602240031
Revises: 202602240030
Create Date: 2026-02-24
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "202602240031"
down_revision = "202602240030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_foreign_key(
        "fk_org_units_tenant_parent_id",
        "org_units",
        "org_units",
        ["tenant_id", "parent_id"],
        ["tenant_id", "id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_user_org_memberships_tenant_user",
        "user_org_memberships",
        "users",
        ["tenant_id", "user_id"],
        ["tenant_id", "id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_user_org_memberships_tenant_org_unit",
        "user_org_memberships",
        "org_units",
        ["tenant_id", "org_unit_id"],
        ["tenant_id", "id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_user_org_memberships_tenant_org_unit",
        "user_org_memberships",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_user_org_memberships_tenant_user",
        "user_org_memberships",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_org_units_tenant_parent_id",
        "org_units",
        type_="foreignkey",
    )

