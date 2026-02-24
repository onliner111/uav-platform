"""phase07b b3 incident alert expand

Revision ID: 202602230020
Revises: 202602230019
Create Date: 2026-02-23
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "202602230020"
down_revision = "202602230019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_incidents_tenant_id_id",
        "incidents",
        ["tenant_id", "id"],
    )
    op.create_index(
        "ix_incidents_tenant_id_id",
        "incidents",
        ["tenant_id", "id"],
    )
    op.create_index(
        "ix_incidents_tenant_linked_task_id",
        "incidents",
        ["tenant_id", "linked_task_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_incidents_tenant_linked_task_id", table_name="incidents")
    op.drop_index("ix_incidents_tenant_id_id", table_name="incidents")
    op.drop_constraint("uq_incidents_tenant_id_id", "incidents", type_="unique")
