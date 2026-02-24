"""phase07b b5 reporting export enforce

Revision ID: 202602240028
Revises: 202602240027
Create Date: 2026-02-24
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "202602240028"
down_revision = "202602240027"
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
        table="approval_records",
        constrained_columns=["approved_by"],
        referred_table="users",
    )

    op.create_foreign_key(
        "fk_approval_records_tenant_approved_by",
        "approval_records",
        "users",
        ["tenant_id", "approved_by"],
        ["tenant_id", "id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_approval_records_tenant_approved_by",
        "approval_records",
        type_="foreignkey",
    )
