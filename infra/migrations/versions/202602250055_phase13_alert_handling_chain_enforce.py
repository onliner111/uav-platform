"""phase13 alert handling chain enforce

Revision ID: 202602250055
Revises: 202602250054
Create Date: 2026-02-25
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "202602250055"
down_revision = "202602250054"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_alert_handling_actions_action_type",
        "alert_handling_actions",
        "action_type IN ('ACK', 'DISPATCH', 'VERIFY', 'REVIEW', 'CLOSE')",
    )
    op.create_foreign_key(
        "fk_alert_handling_actions_tenant_alert",
        "alert_handling_actions",
        "alerts",
        ["tenant_id", "alert_id"],
        ["tenant_id", "id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_alert_handling_actions_tenant_alert",
        "alert_handling_actions",
        type_="foreignkey",
    )
    op.drop_constraint(
        "ck_alert_handling_actions_action_type",
        "alert_handling_actions",
        type_="check",
    )
