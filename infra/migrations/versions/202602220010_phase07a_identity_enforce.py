"""phase07a identity enforce composite constraints

Revision ID: 202602220010
Revises: 202602220009
Create Date: 2026-02-22
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "202602220010"
down_revision = "202602220009"
branch_labels = None
depends_on = None


def _drop_legacy_user_roles_constraints() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    for foreign_key in inspector.get_foreign_keys("user_roles"):
        name = foreign_key.get("name")
        if not name:
            continue
        constrained_columns = foreign_key.get("constrained_columns") or []
        referred_table = foreign_key.get("referred_table")
        if constrained_columns == ["user_id"] and referred_table == "users":
            op.drop_constraint(name, "user_roles", type_="foreignkey")
        elif constrained_columns == ["role_id"] and referred_table == "roles":
            op.drop_constraint(name, "user_roles", type_="foreignkey")

    primary_key = inspector.get_pk_constraint("user_roles")
    primary_key_name = primary_key.get("name")
    primary_key_columns = primary_key.get("constrained_columns") or []
    if primary_key_name and set(primary_key_columns) == {"user_id", "role_id"}:
        op.drop_constraint(primary_key_name, "user_roles", type_="primary")


def upgrade() -> None:
    _drop_legacy_user_roles_constraints()

    op.alter_column("user_roles", "tenant_id", existing_type=sa.String(), nullable=False)
    op.create_primary_key("pk_user_roles", "user_roles", ["tenant_id", "user_id", "role_id"])
    op.create_foreign_key(
        "fk_user_roles_tenant_user",
        "user_roles",
        "users",
        ["tenant_id", "user_id"],
        ["tenant_id", "id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_user_roles_tenant_role",
        "user_roles",
        "roles",
        ["tenant_id", "role_id"],
        ["tenant_id", "id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("fk_user_roles_tenant_role", "user_roles", type_="foreignkey")
    op.drop_constraint("fk_user_roles_tenant_user", "user_roles", type_="foreignkey")
    op.drop_constraint("pk_user_roles", "user_roles", type_="primary")
    op.create_primary_key("pk_user_roles_legacy", "user_roles", ["user_id", "role_id"])
    op.create_foreign_key(
        "fk_user_roles_user_id",
        "user_roles",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_user_roles_role_id",
        "user_roles",
        "roles",
        ["role_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.alter_column("user_roles", "tenant_id", existing_type=sa.String(), nullable=True)
