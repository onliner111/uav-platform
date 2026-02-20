"""command phase5 tables

Revision ID: 202602190005
Revises: 202602190004
Create Date: 2026-02-20
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "202602190005"
down_revision = "202602190004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "command_requests",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("drone_id", sa.String(), nullable=False),
        sa.Column("command_type", sa.String(), nullable=False),
        sa.Column("params", sa.JSON(), nullable=False),
        sa.Column("idempotency_key", sa.String(), nullable=False),
        sa.Column("expect_ack", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("ack_ok", sa.Boolean(), nullable=True),
        sa.Column("ack_message", sa.String(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("issued_by", sa.String(), nullable=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["drone_id"], ["drones.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "idempotency_key",
            name="uq_command_requests_tenant_idempotency",
        ),
    )
    op.create_index("ix_command_requests_tenant_id", "command_requests", ["tenant_id"])
    op.create_index("ix_command_requests_drone_id", "command_requests", ["drone_id"])
    op.create_index("ix_command_requests_command_type", "command_requests", ["command_type"])
    op.create_index(
        "ix_command_requests_idempotency_key",
        "command_requests",
        ["idempotency_key"],
    )
    op.create_index("ix_command_requests_status", "command_requests", ["status"])
    op.create_index("ix_command_requests_issued_by", "command_requests", ["issued_by"])
    op.create_index("ix_command_requests_issued_at", "command_requests", ["issued_at"])
    op.create_index("ix_command_requests_updated_at", "command_requests", ["updated_at"])


def downgrade() -> None:
    op.drop_index("ix_command_requests_updated_at", table_name="command_requests")
    op.drop_index("ix_command_requests_issued_at", table_name="command_requests")
    op.drop_index("ix_command_requests_issued_by", table_name="command_requests")
    op.drop_index("ix_command_requests_status", table_name="command_requests")
    op.drop_index("ix_command_requests_idempotency_key", table_name="command_requests")
    op.drop_index("ix_command_requests_command_type", table_name="command_requests")
    op.drop_index("ix_command_requests_drone_id", table_name="command_requests")
    op.drop_index("ix_command_requests_tenant_id", table_name="command_requests")
    op.drop_table("command_requests")
