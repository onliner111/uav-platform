"""phase07a identity expand schema

Revision ID: 202602220008
Revises: 202602210007
Create Date: 2026-02-22
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "202602220008"
down_revision = "202602210007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("user_roles", sa.Column("tenant_id", sa.String(), nullable=True))
    op.create_index("ix_user_roles_tenant_user", "user_roles", ["tenant_id", "user_id"])
    op.create_index("ix_user_roles_tenant_role", "user_roles", ["tenant_id", "role_id"])
    op.create_unique_constraint("uq_users_tenant_id_id", "users", ["tenant_id", "id"])
    op.create_unique_constraint("uq_roles_tenant_id_id", "roles", ["tenant_id", "id"])


def downgrade() -> None:
    op.drop_constraint("uq_roles_tenant_id_id", "roles", type_="unique")
    op.drop_constraint("uq_users_tenant_id_id", "users", type_="unique")
    op.drop_index("ix_user_roles_tenant_role", table_name="user_roles")
    op.drop_index("ix_user_roles_tenant_user", table_name="user_roles")
    op.drop_column("user_roles", "tenant_id")
