"""phase07b b2 defect expand

Revision ID: 202602230017
Revises: 202602230016
Create Date: 2026-02-23
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "202602230017"
down_revision = "202602230016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint("uq_defects_tenant_id_id", "defects", ["tenant_id", "id"])
    op.create_unique_constraint(
        "uq_defect_actions_tenant_id_id",
        "defect_actions",
        ["tenant_id", "id"],
    )

    op.create_index("ix_defects_tenant_id_id", "defects", ["tenant_id", "id"])
    op.create_index(
        "ix_defects_tenant_observation_id",
        "defects",
        ["tenant_id", "observation_id"],
    )
    op.create_index(
        "ix_defect_actions_tenant_id_id",
        "defect_actions",
        ["tenant_id", "id"],
    )
    op.create_index(
        "ix_defect_actions_tenant_defect_id",
        "defect_actions",
        ["tenant_id", "defect_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_defect_actions_tenant_defect_id", table_name="defect_actions")
    op.drop_index("ix_defect_actions_tenant_id_id", table_name="defect_actions")
    op.drop_index("ix_defects_tenant_observation_id", table_name="defects")
    op.drop_index("ix_defects_tenant_id_id", table_name="defects")

    op.drop_constraint("uq_defect_actions_tenant_id_id", "defect_actions", type_="unique")
    op.drop_constraint("uq_defects_tenant_id_id", "defects", type_="unique")
