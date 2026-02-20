"""alert phase7 tables

Revision ID: 202602190006
Revises: 202602190005
Create Date: 2026-02-20
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "202602190006"
down_revision = "202602190005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "alerts",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("drone_id", sa.String(), nullable=False),
        sa.Column("alert_type", sa.String(), nullable=False),
        sa.Column("severity", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("message", sa.String(), nullable=False),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("acked_by", sa.String(), nullable=True),
        sa.Column("acked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_by", sa.String(), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_alerts_tenant_id", "alerts", ["tenant_id"])
    op.create_index("ix_alerts_drone_id", "alerts", ["drone_id"])
    op.create_index("ix_alerts_alert_type", "alerts", ["alert_type"])
    op.create_index("ix_alerts_severity", "alerts", ["severity"])
    op.create_index("ix_alerts_status", "alerts", ["status"])
    op.create_index("ix_alerts_first_seen_at", "alerts", ["first_seen_at"])
    op.create_index("ix_alerts_last_seen_at", "alerts", ["last_seen_at"])
    op.create_index("ix_alerts_acked_by", "alerts", ["acked_by"])
    op.create_index("ix_alerts_acked_at", "alerts", ["acked_at"])
    op.create_index("ix_alerts_closed_by", "alerts", ["closed_by"])
    op.create_index("ix_alerts_closed_at", "alerts", ["closed_at"])


def downgrade() -> None:
    op.drop_index("ix_alerts_closed_at", table_name="alerts")
    op.drop_index("ix_alerts_closed_by", table_name="alerts")
    op.drop_index("ix_alerts_acked_at", table_name="alerts")
    op.drop_index("ix_alerts_acked_by", table_name="alerts")
    op.drop_index("ix_alerts_last_seen_at", table_name="alerts")
    op.drop_index("ix_alerts_first_seen_at", table_name="alerts")
    op.drop_index("ix_alerts_status", table_name="alerts")
    op.drop_index("ix_alerts_severity", table_name="alerts")
    op.drop_index("ix_alerts_alert_type", table_name="alerts")
    op.drop_index("ix_alerts_drone_id", table_name="alerts")
    op.drop_index("ix_alerts_tenant_id", table_name="alerts")
    op.drop_table("alerts")
