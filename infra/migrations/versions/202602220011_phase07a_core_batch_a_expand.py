"""phase07a core batch a expand

Revision ID: 202602220011
Revises: 202602220010
Create Date: 2026-02-22
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "202602220011"
down_revision = "202602220010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint("uq_drones_tenant_id_id", "drones", ["tenant_id", "id"])
    op.create_unique_constraint("uq_missions_tenant_id_id", "missions", ["tenant_id", "id"])

    op.create_index("ix_missions_tenant_drone_id", "missions", ["tenant_id", "drone_id"])
    op.create_index("ix_missions_tenant_state", "missions", ["tenant_id", "state"])
    op.create_index("ix_mission_runs_tenant_mission_id", "mission_runs", ["tenant_id", "mission_id"])


def downgrade() -> None:
    op.drop_index("ix_mission_runs_tenant_mission_id", table_name="mission_runs")
    op.drop_index("ix_missions_tenant_state", table_name="missions")
    op.drop_index("ix_missions_tenant_drone_id", table_name="missions")

    op.drop_constraint("uq_missions_tenant_id_id", "missions", type_="unique")
    op.drop_constraint("uq_drones_tenant_id_id", "drones", type_="unique")
