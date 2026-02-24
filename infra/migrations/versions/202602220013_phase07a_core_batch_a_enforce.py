"""phase07a core batch a enforce

Revision ID: 202602220013
Revises: 202602220012
Create Date: 2026-02-22
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "202602220013"
down_revision = "202602220012"
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
    _drop_legacy_fk(table="missions", constrained_columns=["drone_id"], referred_table="drones")
    _drop_legacy_fk(table="mission_runs", constrained_columns=["mission_id"], referred_table="missions")

    op.create_foreign_key(
        "fk_missions_tenant_drone",
        "missions",
        "drones",
        ["tenant_id", "drone_id"],
        ["tenant_id", "id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_mission_runs_tenant_mission",
        "mission_runs",
        "missions",
        ["tenant_id", "mission_id"],
        ["tenant_id", "id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint("fk_mission_runs_tenant_mission", "mission_runs", type_="foreignkey")
    op.drop_constraint("fk_missions_tenant_drone", "missions", type_="foreignkey")

    op.create_foreign_key(
        "fk_missions_drone_id",
        "missions",
        "drones",
        ["drone_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_mission_runs_mission_id",
        "mission_runs",
        "missions",
        ["mission_id"],
        ["id"],
        ondelete="CASCADE",
    )
