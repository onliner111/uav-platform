"""phase08b data perimeter expand

Revision ID: 202602240032
Revises: 202602240031
Create Date: 2026-02-24
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "202602240032"
down_revision = "202602240031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "data_access_policies",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("scope_mode", sa.String(length=20), nullable=False),
        sa.Column("org_unit_ids", sa.JSON(), nullable=False),
        sa.Column("project_codes", sa.JSON(), nullable=False),
        sa.Column("area_codes", sa.JSON(), nullable=False),
        sa.Column("task_ids", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "user_id", name="uq_data_access_policies_tenant_user"),
    )
    op.create_index("ix_data_access_policies_tenant_id", "data_access_policies", ["tenant_id"])
    op.create_index("ix_data_access_policies_user_id", "data_access_policies", ["user_id"])
    op.create_index("ix_data_access_policies_scope_mode", "data_access_policies", ["scope_mode"])
    op.create_index(
        "ix_data_access_policies_tenant_user",
        "data_access_policies",
        ["tenant_id", "user_id"],
    )
    op.create_index("ix_data_access_policies_created_at", "data_access_policies", ["created_at"])
    op.create_index("ix_data_access_policies_updated_at", "data_access_policies", ["updated_at"])

    op.add_column("missions", sa.Column("org_unit_id", sa.String(), nullable=True))
    op.add_column("missions", sa.Column("project_code", sa.String(length=100), nullable=True))
    op.add_column("missions", sa.Column("area_code", sa.String(length=100), nullable=True))
    op.create_index("ix_missions_org_unit_id", "missions", ["org_unit_id"])
    op.create_index("ix_missions_project_code", "missions", ["project_code"])
    op.create_index("ix_missions_area_code", "missions", ["area_code"])
    op.create_index("ix_missions_tenant_org_unit", "missions", ["tenant_id", "org_unit_id"])

    op.add_column("inspection_tasks", sa.Column("org_unit_id", sa.String(), nullable=True))
    op.add_column("inspection_tasks", sa.Column("project_code", sa.String(length=100), nullable=True))
    op.add_column("inspection_tasks", sa.Column("area_code", sa.String(length=100), nullable=True))
    op.create_index("ix_inspection_tasks_org_unit_id", "inspection_tasks", ["org_unit_id"])
    op.create_index("ix_inspection_tasks_project_code", "inspection_tasks", ["project_code"])
    op.create_index("ix_inspection_tasks_area_code", "inspection_tasks", ["area_code"])
    op.create_index(
        "ix_inspection_tasks_tenant_org_unit",
        "inspection_tasks",
        ["tenant_id", "org_unit_id"],
    )

    op.add_column("defects", sa.Column("task_id", sa.String(), nullable=True))
    op.add_column("defects", sa.Column("org_unit_id", sa.String(), nullable=True))
    op.add_column("defects", sa.Column("project_code", sa.String(length=100), nullable=True))
    op.add_column("defects", sa.Column("area_code", sa.String(length=100), nullable=True))
    op.create_index("ix_defects_task_id", "defects", ["task_id"])
    op.create_index("ix_defects_org_unit_id", "defects", ["org_unit_id"])
    op.create_index("ix_defects_project_code", "defects", ["project_code"])
    op.create_index("ix_defects_area_code", "defects", ["area_code"])
    op.create_index("ix_defects_tenant_task_id", "defects", ["tenant_id", "task_id"])
    op.create_index("ix_defects_tenant_org_unit", "defects", ["tenant_id", "org_unit_id"])

    op.add_column("incidents", sa.Column("org_unit_id", sa.String(), nullable=True))
    op.add_column("incidents", sa.Column("project_code", sa.String(length=100), nullable=True))
    op.add_column("incidents", sa.Column("area_code", sa.String(length=100), nullable=True))
    op.create_index("ix_incidents_org_unit_id", "incidents", ["org_unit_id"])
    op.create_index("ix_incidents_project_code", "incidents", ["project_code"])
    op.create_index("ix_incidents_area_code", "incidents", ["area_code"])
    op.create_index("ix_incidents_tenant_org_unit", "incidents", ["tenant_id", "org_unit_id"])


def downgrade() -> None:
    op.drop_index("ix_incidents_tenant_org_unit", table_name="incidents")
    op.drop_index("ix_incidents_area_code", table_name="incidents")
    op.drop_index("ix_incidents_project_code", table_name="incidents")
    op.drop_index("ix_incidents_org_unit_id", table_name="incidents")
    op.drop_column("incidents", "area_code")
    op.drop_column("incidents", "project_code")
    op.drop_column("incidents", "org_unit_id")

    op.drop_index("ix_defects_tenant_org_unit", table_name="defects")
    op.drop_index("ix_defects_tenant_task_id", table_name="defects")
    op.drop_index("ix_defects_area_code", table_name="defects")
    op.drop_index("ix_defects_project_code", table_name="defects")
    op.drop_index("ix_defects_org_unit_id", table_name="defects")
    op.drop_index("ix_defects_task_id", table_name="defects")
    op.drop_column("defects", "area_code")
    op.drop_column("defects", "project_code")
    op.drop_column("defects", "org_unit_id")
    op.drop_column("defects", "task_id")

    op.drop_index("ix_inspection_tasks_tenant_org_unit", table_name="inspection_tasks")
    op.drop_index("ix_inspection_tasks_area_code", table_name="inspection_tasks")
    op.drop_index("ix_inspection_tasks_project_code", table_name="inspection_tasks")
    op.drop_index("ix_inspection_tasks_org_unit_id", table_name="inspection_tasks")
    op.drop_column("inspection_tasks", "area_code")
    op.drop_column("inspection_tasks", "project_code")
    op.drop_column("inspection_tasks", "org_unit_id")

    op.drop_index("ix_missions_tenant_org_unit", table_name="missions")
    op.drop_index("ix_missions_area_code", table_name="missions")
    op.drop_index("ix_missions_project_code", table_name="missions")
    op.drop_index("ix_missions_org_unit_id", table_name="missions")
    op.drop_column("missions", "area_code")
    op.drop_column("missions", "project_code")
    op.drop_column("missions", "org_unit_id")

    op.drop_index("ix_data_access_policies_updated_at", table_name="data_access_policies")
    op.drop_index("ix_data_access_policies_created_at", table_name="data_access_policies")
    op.drop_index("ix_data_access_policies_tenant_user", table_name="data_access_policies")
    op.drop_index("ix_data_access_policies_scope_mode", table_name="data_access_policies")
    op.drop_index("ix_data_access_policies_user_id", table_name="data_access_policies")
    op.drop_index("ix_data_access_policies_tenant_id", table_name="data_access_policies")
    op.drop_table("data_access_policies")
