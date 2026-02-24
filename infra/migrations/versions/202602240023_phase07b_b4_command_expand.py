"""phase07b b4 command expand

Revision ID: 202602240023
Revises: 202602230022
Create Date: 2026-02-24
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "202602240023"
down_revision = "202602230022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_command_requests_tenant_id_id",
        "command_requests",
        ["tenant_id", "id"],
    )
    op.create_index(
        "ix_command_requests_tenant_id_id",
        "command_requests",
        ["tenant_id", "id"],
    )
    op.create_index(
        "ix_command_requests_tenant_drone_id",
        "command_requests",
        ["tenant_id", "drone_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_command_requests_tenant_drone_id", table_name="command_requests")
    op.drop_index("ix_command_requests_tenant_id_id", table_name="command_requests")
    op.drop_constraint(
        "uq_command_requests_tenant_id_id",
        "command_requests",
        type_="unique",
    )

