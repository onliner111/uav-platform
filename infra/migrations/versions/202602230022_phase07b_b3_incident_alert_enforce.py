"""phase07b b3 incident alert enforce

Revision ID: 202602230022
Revises: 202602230021
Create Date: 2026-02-23
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "202602230022"
down_revision = "202602230021"
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
        table="incidents",
        constrained_columns=["linked_task_id"],
        referred_table="inspection_tasks",
    )

    op.create_foreign_key(
        "fk_incidents_tenant_linked_task",
        "incidents",
        "inspection_tasks",
        ["tenant_id", "linked_task_id"],
        ["tenant_id", "id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint("fk_incidents_tenant_linked_task", "incidents", type_="foreignkey")

    op.create_foreign_key(
        "fk_incidents_linked_task_id",
        "incidents",
        "inspection_tasks",
        ["linked_task_id"],
        ["id"],
        ondelete="SET NULL",
    )
