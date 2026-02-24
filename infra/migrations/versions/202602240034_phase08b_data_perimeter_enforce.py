"""phase08b data perimeter enforce

Revision ID: 202602240034
Revises: 202602240033
Create Date: 2026-02-24
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "202602240034"
down_revision = "202602240033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_foreign_key(
        "fk_data_access_policies_tenant_user",
        "data_access_policies",
        "users",
        ["tenant_id", "user_id"],
        ["tenant_id", "id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_missions_tenant_org_unit",
        "missions",
        "org_units",
        ["tenant_id", "org_unit_id"],
        ["tenant_id", "id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_inspection_tasks_tenant_org_unit",
        "inspection_tasks",
        "org_units",
        ["tenant_id", "org_unit_id"],
        ["tenant_id", "id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_defects_tenant_task",
        "defects",
        "inspection_tasks",
        ["tenant_id", "task_id"],
        ["tenant_id", "id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_defects_tenant_org_unit",
        "defects",
        "org_units",
        ["tenant_id", "org_unit_id"],
        ["tenant_id", "id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_incidents_tenant_org_unit",
        "incidents",
        "org_units",
        ["tenant_id", "org_unit_id"],
        ["tenant_id", "id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint("fk_incidents_tenant_org_unit", "incidents", type_="foreignkey")
    op.drop_constraint("fk_defects_tenant_org_unit", "defects", type_="foreignkey")
    op.drop_constraint("fk_defects_tenant_task", "defects", type_="foreignkey")
    op.drop_constraint("fk_inspection_tasks_tenant_org_unit", "inspection_tasks", type_="foreignkey")
    op.drop_constraint("fk_missions_tenant_org_unit", "missions", type_="foreignkey")
    op.drop_constraint("fk_data_access_policies_tenant_user", "data_access_policies", type_="foreignkey")
