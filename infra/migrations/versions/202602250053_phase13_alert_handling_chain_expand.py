"""phase13 alert handling chain expand

Revision ID: 202602250053
Revises: 202602250052
Create Date: 2026-02-25
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "202602250053"
down_revision = "202602250052"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "alert_handling_actions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("alert_id", sa.String(), nullable=False),
        sa.Column("action_type", sa.String(length=20), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("actor_id", sa.String(), nullable=True),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_alert_handling_actions_tenant_id_id"),
    )
    op.create_index("ix_alert_handling_actions_tenant_id", "alert_handling_actions", ["tenant_id"])
    op.create_index("ix_alert_handling_actions_alert_id", "alert_handling_actions", ["alert_id"])
    op.create_index("ix_alert_handling_actions_action_type", "alert_handling_actions", ["action_type"])
    op.create_index("ix_alert_handling_actions_actor_id", "alert_handling_actions", ["actor_id"])
    op.create_index("ix_alert_handling_actions_created_at", "alert_handling_actions", ["created_at"])
    op.create_index("ix_alert_handling_actions_tenant_id_id", "alert_handling_actions", ["tenant_id", "id"])
    op.create_index("ix_alert_handling_actions_tenant_alert", "alert_handling_actions", ["tenant_id", "alert_id"])


def downgrade() -> None:
    op.drop_index("ix_alert_handling_actions_tenant_alert", table_name="alert_handling_actions")
    op.drop_index("ix_alert_handling_actions_tenant_id_id", table_name="alert_handling_actions")
    op.drop_index("ix_alert_handling_actions_created_at", table_name="alert_handling_actions")
    op.drop_index("ix_alert_handling_actions_actor_id", table_name="alert_handling_actions")
    op.drop_index("ix_alert_handling_actions_action_type", table_name="alert_handling_actions")
    op.drop_index("ix_alert_handling_actions_alert_id", table_name="alert_handling_actions")
    op.drop_index("ix_alert_handling_actions_tenant_id", table_name="alert_handling_actions")
    op.drop_table("alert_handling_actions")
