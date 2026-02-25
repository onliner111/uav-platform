"""phase11 task center p0 enforce

Revision ID: 202602240046
Revises: 202602240045
Create Date: 2026-02-25
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "202602240046"
down_revision = "202602240045"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_task_templates_default_priority_range",
        "task_templates",
        "default_priority >= 1 AND default_priority <= 10",
    )
    op.create_check_constraint(
        "ck_task_templates_default_risk_range",
        "task_templates",
        "default_risk_level >= 1 AND default_risk_level <= 5",
    )
    op.create_check_constraint(
        "ck_task_center_tasks_priority_range",
        "task_center_tasks",
        "priority >= 1 AND priority <= 10",
    )
    op.create_check_constraint(
        "ck_task_center_tasks_risk_range",
        "task_center_tasks",
        "risk_level >= 1 AND risk_level <= 5",
    )

    op.create_foreign_key(
        "fk_task_templates_tenant_task_type",
        "task_templates",
        "task_type_catalogs",
        ["tenant_id", "task_type_id"],
        ["tenant_id", "id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_task_center_tasks_tenant_task_type",
        "task_center_tasks",
        "task_type_catalogs",
        ["tenant_id", "task_type_id"],
        ["tenant_id", "id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_task_center_tasks_tenant_template",
        "task_center_tasks",
        "task_templates",
        ["tenant_id", "template_id"],
        ["tenant_id", "id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_task_center_tasks_tenant_org_unit",
        "task_center_tasks",
        "org_units",
        ["tenant_id", "org_unit_id"],
        ["tenant_id", "id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_task_center_tasks_tenant_mission",
        "task_center_tasks",
        "missions",
        ["tenant_id", "mission_id"],
        ["tenant_id", "id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_task_center_tasks_tenant_assigned_user",
        "task_center_tasks",
        "users",
        ["tenant_id", "assigned_to"],
        ["tenant_id", "id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_task_center_task_histories_tenant_task",
        "task_center_task_histories",
        "task_center_tasks",
        ["tenant_id", "task_id"],
        ["tenant_id", "id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_task_center_task_histories_tenant_task",
        "task_center_task_histories",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_task_center_tasks_tenant_assigned_user",
        "task_center_tasks",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_task_center_tasks_tenant_mission",
        "task_center_tasks",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_task_center_tasks_tenant_org_unit",
        "task_center_tasks",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_task_center_tasks_tenant_template",
        "task_center_tasks",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_task_center_tasks_tenant_task_type",
        "task_center_tasks",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_task_templates_tenant_task_type",
        "task_templates",
        type_="foreignkey",
    )

    op.drop_constraint(
        "ck_task_center_tasks_risk_range",
        "task_center_tasks",
        type_="check",
    )
    op.drop_constraint(
        "ck_task_center_tasks_priority_range",
        "task_center_tasks",
        type_="check",
    )
    op.drop_constraint(
        "ck_task_templates_default_risk_range",
        "task_templates",
        type_="check",
    )
    op.drop_constraint(
        "ck_task_templates_default_priority_range",
        "task_templates",
        type_="check",
    )
