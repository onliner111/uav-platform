"""phase07b b1 inspection enforce

Revision ID: 202602230016
Revises: 202602230015
Create Date: 2026-02-23
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "202602230016"
down_revision = "202602230015"
branch_labels = None
depends_on = None


def _drop_legacy_fk(
    *,
    table: str,
    constrained_columns: list[str],
    referred_table: str,
) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for foreign_key in inspector.get_foreign_keys(table):
        name = foreign_key.get("name")
        if not name:
            continue
        fk_columns = foreign_key.get("constrained_columns") or []
        fk_referred_table = foreign_key.get("referred_table")
        if fk_columns == constrained_columns and fk_referred_table == referred_table:
            op.drop_constraint(name, table, type_="foreignkey")


def upgrade() -> None:
    _drop_legacy_fk(
        table="inspection_template_items",
        constrained_columns=["template_id"],
        referred_table="inspection_templates",
    )
    _drop_legacy_fk(
        table="inspection_tasks",
        constrained_columns=["template_id"],
        referred_table="inspection_templates",
    )

    op.create_foreign_key(
        "fk_inspection_template_items_tenant_template",
        "inspection_template_items",
        "inspection_templates",
        ["tenant_id", "template_id"],
        ["tenant_id", "id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_inspection_tasks_tenant_template",
        "inspection_tasks",
        "inspection_templates",
        ["tenant_id", "template_id"],
        ["tenant_id", "id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_inspection_tasks_tenant_template",
        "inspection_tasks",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_inspection_template_items_tenant_template",
        "inspection_template_items",
        type_="foreignkey",
    )

    op.create_foreign_key(
        "fk_inspection_template_items_template_id",
        "inspection_template_items",
        "inspection_templates",
        ["template_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_inspection_tasks_template_id",
        "inspection_tasks",
        "inspection_templates",
        ["template_id"],
        ["id"],
        ondelete="RESTRICT",
    )
