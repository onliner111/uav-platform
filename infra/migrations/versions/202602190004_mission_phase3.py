"""mission phase3 tables

Revision ID: 202602190004
Revises: 202602190003
Create Date: 2026-02-19
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "202602190004"
down_revision = "202602190003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "missions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("drone_id", sa.String(), nullable=True),
        sa.Column("plan_type", sa.String(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("constraints", sa.JSON(), nullable=False),
        sa.Column("state", sa.String(), nullable=False),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["drone_id"], ["drones.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_missions_tenant_id", "missions", ["tenant_id"])
    op.create_index("ix_missions_name", "missions", ["name"])
    op.create_index("ix_missions_drone_id", "missions", ["drone_id"])
    op.create_index("ix_missions_state", "missions", ["state"])
    op.create_index("ix_missions_created_at", "missions", ["created_at"])
    op.create_index("ix_missions_updated_at", "missions", ["updated_at"])

    op.create_table(
        "approvals",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("mission_id", sa.String(), nullable=False),
        sa.Column("approver_id", sa.String(), nullable=False),
        sa.Column("decision", sa.String(), nullable=False),
        sa.Column("comment", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["mission_id"], ["missions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_approvals_tenant_id", "approvals", ["tenant_id"])
    op.create_index("ix_approvals_mission_id", "approvals", ["mission_id"])
    op.create_index("ix_approvals_approver_id", "approvals", ["approver_id"])
    op.create_index("ix_approvals_created_at", "approvals", ["created_at"])

    op.create_table(
        "mission_runs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("mission_id", sa.String(), nullable=False),
        sa.Column("state", sa.String(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["mission_id"], ["missions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mission_runs_tenant_id", "mission_runs", ["tenant_id"])
    op.create_index("ix_mission_runs_mission_id", "mission_runs", ["mission_id"])
    op.create_index("ix_mission_runs_state", "mission_runs", ["state"])
    op.create_index("ix_mission_runs_started_at", "mission_runs", ["started_at"])
    op.create_index("ix_mission_runs_ended_at", "mission_runs", ["ended_at"])


def downgrade() -> None:
    op.drop_index("ix_mission_runs_ended_at", table_name="mission_runs")
    op.drop_index("ix_mission_runs_started_at", table_name="mission_runs")
    op.drop_index("ix_mission_runs_state", table_name="mission_runs")
    op.drop_index("ix_mission_runs_mission_id", table_name="mission_runs")
    op.drop_index("ix_mission_runs_tenant_id", table_name="mission_runs")
    op.drop_table("mission_runs")

    op.drop_index("ix_approvals_created_at", table_name="approvals")
    op.drop_index("ix_approvals_approver_id", table_name="approvals")
    op.drop_index("ix_approvals_mission_id", table_name="approvals")
    op.drop_index("ix_approvals_tenant_id", table_name="approvals")
    op.drop_table("approvals")

    op.drop_index("ix_missions_updated_at", table_name="missions")
    op.drop_index("ix_missions_created_at", table_name="missions")
    op.drop_index("ix_missions_state", table_name="missions")
    op.drop_index("ix_missions_drone_id", table_name="missions")
    op.drop_index("ix_missions_name", table_name="missions")
    op.drop_index("ix_missions_tenant_id", table_name="missions")
    op.drop_table("missions")

