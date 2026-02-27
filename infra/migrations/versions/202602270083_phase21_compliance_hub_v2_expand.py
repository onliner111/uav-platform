"""phase21 compliance hub v2 expand

Revision ID: 202602270083
Revises: 202602260082
Create Date: 2026-02-27
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "202602270083"
down_revision = "202602260082"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("airspace_zones", sa.Column("policy_layer", sa.String(length=32), nullable=True))
    op.add_column("airspace_zones", sa.Column("policy_effect", sa.String(length=16), nullable=True))
    op.add_column("airspace_zones", sa.Column("org_unit_id", sa.String(), nullable=True))
    op.create_index("ix_airspace_zones_policy_layer", "airspace_zones", ["policy_layer"])
    op.create_index("ix_airspace_zones_policy_effect", "airspace_zones", ["policy_effect"])
    op.create_index("ix_airspace_zones_org_unit_id", "airspace_zones", ["org_unit_id"])

    op.add_column(
        "preflight_checklist_templates",
        sa.Column("template_version", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "preflight_checklist_templates",
        sa.Column("evidence_requirements", sa.JSON(), nullable=True),
    )

    op.create_table(
        "compliance_approval_flow_templates",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("steps", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "id",
            name="uq_compliance_approval_flow_templates_tenant_id_id",
        ),
    )
    op.create_index(
        "ix_compliance_approval_flow_templates_tenant_id_id",
        "compliance_approval_flow_templates",
        ["tenant_id", "id"],
    )
    op.create_index(
        "ix_compliance_approval_flow_templates_tenant_entity",
        "compliance_approval_flow_templates",
        ["tenant_id", "entity_type"],
    )

    op.create_table(
        "compliance_approval_flow_instances",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("template_id", sa.String(), nullable=False),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("entity_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("current_step_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("steps_snapshot", sa.JSON(), nullable=False),
        sa.Column("action_history", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "id",
            name="uq_compliance_approval_flow_instances_tenant_id_id",
        ),
    )
    op.create_index(
        "ix_compliance_approval_flow_instances_tenant_id_id",
        "compliance_approval_flow_instances",
        ["tenant_id", "id"],
    )
    op.create_index(
        "ix_compliance_approval_flow_instances_tenant_entity",
        "compliance_approval_flow_instances",
        ["tenant_id", "entity_type", "entity_id"],
    )
    op.create_index(
        "ix_compliance_approval_flow_instances_template_id",
        "compliance_approval_flow_instances",
        ["template_id"],
    )
    op.create_index(
        "ix_compliance_approval_flow_instances_status",
        "compliance_approval_flow_instances",
        ["status"],
    )

    op.create_table(
        "compliance_decision_records",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("entity_id", sa.String(), nullable=False),
        sa.Column("decision", sa.String(length=20), nullable=False),
        sa.Column("reason_code", sa.String(length=100), nullable=True),
        sa.Column("actor_id", sa.String(), nullable=True),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "id",
            name="uq_compliance_decision_records_tenant_id_id",
        ),
    )
    op.create_index(
        "ix_compliance_decision_records_tenant_id_id",
        "compliance_decision_records",
        ["tenant_id", "id"],
    )
    op.create_index(
        "ix_compliance_decision_records_tenant_entity",
        "compliance_decision_records",
        ["tenant_id", "entity_type", "entity_id"],
    )
    op.create_index(
        "ix_compliance_decision_records_tenant_source",
        "compliance_decision_records",
        ["tenant_id", "source"],
    )
    op.create_index(
        "ix_compliance_decision_records_reason_code",
        "compliance_decision_records",
        ["reason_code"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_compliance_decision_records_reason_code",
        table_name="compliance_decision_records",
    )
    op.drop_index(
        "ix_compliance_decision_records_tenant_source",
        table_name="compliance_decision_records",
    )
    op.drop_index(
        "ix_compliance_decision_records_tenant_entity",
        table_name="compliance_decision_records",
    )
    op.drop_index(
        "ix_compliance_decision_records_tenant_id_id",
        table_name="compliance_decision_records",
    )
    op.drop_table("compliance_decision_records")

    op.drop_index(
        "ix_compliance_approval_flow_instances_status",
        table_name="compliance_approval_flow_instances",
    )
    op.drop_index(
        "ix_compliance_approval_flow_instances_template_id",
        table_name="compliance_approval_flow_instances",
    )
    op.drop_index(
        "ix_compliance_approval_flow_instances_tenant_entity",
        table_name="compliance_approval_flow_instances",
    )
    op.drop_index(
        "ix_compliance_approval_flow_instances_tenant_id_id",
        table_name="compliance_approval_flow_instances",
    )
    op.drop_table("compliance_approval_flow_instances")

    op.drop_index(
        "ix_compliance_approval_flow_templates_tenant_entity",
        table_name="compliance_approval_flow_templates",
    )
    op.drop_index(
        "ix_compliance_approval_flow_templates_tenant_id_id",
        table_name="compliance_approval_flow_templates",
    )
    op.drop_table("compliance_approval_flow_templates")

    op.drop_column("preflight_checklist_templates", "evidence_requirements")
    op.drop_column("preflight_checklist_templates", "template_version")

    op.drop_index("ix_airspace_zones_org_unit_id", table_name="airspace_zones")
    op.drop_index("ix_airspace_zones_policy_effect", table_name="airspace_zones")
    op.drop_index("ix_airspace_zones_policy_layer", table_name="airspace_zones")
    op.drop_column("airspace_zones", "org_unit_id")
    op.drop_column("airspace_zones", "policy_effect")
    op.drop_column("airspace_zones", "policy_layer")
