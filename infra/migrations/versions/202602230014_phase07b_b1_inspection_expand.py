"""phase07b b1 inspection expand

Revision ID: 202602230014
Revises: 202602220013
Create Date: 2026-02-23
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "202602230014"
down_revision = "202602220013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_inspection_templates_tenant_id_id",
        "inspection_templates",
        ["tenant_id", "id"],
    )
    op.create_unique_constraint(
        "uq_inspection_template_items_tenant_id_id",
        "inspection_template_items",
        ["tenant_id", "id"],
    )
    op.create_unique_constraint(
        "uq_inspection_tasks_tenant_id_id",
        "inspection_tasks",
        ["tenant_id", "id"],
    )

    op.create_index(
        "ix_inspection_templates_tenant_id_id",
        "inspection_templates",
        ["tenant_id", "id"],
    )
    op.create_index(
        "ix_inspection_template_items_tenant_id_id",
        "inspection_template_items",
        ["tenant_id", "id"],
    )
    op.create_index(
        "ix_inspection_template_items_tenant_template_id",
        "inspection_template_items",
        ["tenant_id", "template_id"],
    )
    op.create_index(
        "ix_inspection_tasks_tenant_id_id",
        "inspection_tasks",
        ["tenant_id", "id"],
    )
    op.create_index(
        "ix_inspection_tasks_tenant_template_id",
        "inspection_tasks",
        ["tenant_id", "template_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_inspection_tasks_tenant_template_id", table_name="inspection_tasks")
    op.drop_index("ix_inspection_tasks_tenant_id_id", table_name="inspection_tasks")
    op.drop_index(
        "ix_inspection_template_items_tenant_template_id",
        table_name="inspection_template_items",
    )
    op.drop_index(
        "ix_inspection_template_items_tenant_id_id",
        table_name="inspection_template_items",
    )
    op.drop_index("ix_inspection_templates_tenant_id_id", table_name="inspection_templates")

    op.drop_constraint("uq_inspection_tasks_tenant_id_id", "inspection_tasks", type_="unique")
    op.drop_constraint(
        "uq_inspection_template_items_tenant_id_id",
        "inspection_template_items",
        type_="unique",
    )
    op.drop_constraint(
        "uq_inspection_templates_tenant_id_id",
        "inspection_templates",
        type_="unique",
    )
