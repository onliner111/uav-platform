"""phase21 compliance hub v2 enforce

Revision ID: 202602270085
Revises: 202602270084
Create Date: 2026-02-27
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "202602270085"
down_revision = "202602270084"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "airspace_zones",
        "policy_layer",
        existing_type=sa.String(length=32),
        nullable=False,
    )
    op.alter_column(
        "airspace_zones",
        "policy_effect",
        existing_type=sa.String(length=16),
        nullable=False,
    )
    op.alter_column(
        "preflight_checklist_templates",
        "template_version",
        existing_type=sa.String(length=50),
        nullable=False,
    )
    op.alter_column(
        "preflight_checklist_templates",
        "evidence_requirements",
        existing_type=sa.JSON(),
        nullable=False,
    )

    op.create_check_constraint(
        "ck_airspace_zones_policy_layer",
        "airspace_zones",
        "policy_layer IN ('PLATFORM_DEFAULT', 'TENANT', 'ORG_UNIT')",
    )
    op.create_check_constraint(
        "ck_airspace_zones_policy_effect",
        "airspace_zones",
        "policy_effect IN ('ALLOW', 'DENY')",
    )
    op.create_check_constraint(
        "ck_preflight_templates_template_version_not_empty",
        "preflight_checklist_templates",
        "template_version <> ''",
    )
    op.create_check_constraint(
        "ck_approval_flow_instances_status",
        "compliance_approval_flow_instances",
        "status IN ('PENDING', 'APPROVED', 'REJECTED')",
    )
    op.create_check_constraint(
        "ck_approval_flow_instances_current_step_non_negative",
        "compliance_approval_flow_instances",
        "current_step_index >= 0",
    )
    op.create_check_constraint(
        "ck_compliance_decision_records_decision",
        "compliance_decision_records",
        "decision IN ('ALLOW', 'DENY', 'APPROVE', 'REJECT')",
    )

    op.create_foreign_key(
        "fk_compliance_approval_flow_instances_tenant_template",
        "compliance_approval_flow_instances",
        "compliance_approval_flow_templates",
        ["tenant_id", "template_id"],
        ["tenant_id", "id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_compliance_approval_flow_instances_tenant_template",
        "compliance_approval_flow_instances",
        type_="foreignkey",
    )
    op.drop_constraint(
        "ck_compliance_decision_records_decision",
        "compliance_decision_records",
        type_="check",
    )
    op.drop_constraint(
        "ck_approval_flow_instances_current_step_non_negative",
        "compliance_approval_flow_instances",
        type_="check",
    )
    op.drop_constraint(
        "ck_approval_flow_instances_status",
        "compliance_approval_flow_instances",
        type_="check",
    )
    op.drop_constraint(
        "ck_preflight_templates_template_version_not_empty",
        "preflight_checklist_templates",
        type_="check",
    )
    op.drop_constraint(
        "ck_airspace_zones_policy_effect",
        "airspace_zones",
        type_="check",
    )
    op.drop_constraint(
        "ck_airspace_zones_policy_layer",
        "airspace_zones",
        type_="check",
    )

    op.alter_column(
        "preflight_checklist_templates",
        "evidence_requirements",
        existing_type=sa.JSON(),
        nullable=True,
    )
    op.alter_column(
        "preflight_checklist_templates",
        "template_version",
        existing_type=sa.String(length=50),
        nullable=True,
    )
    op.alter_column(
        "airspace_zones",
        "policy_effect",
        existing_type=sa.String(length=16),
        nullable=True,
    )
    op.alter_column(
        "airspace_zones",
        "policy_layer",
        existing_type=sa.String(length=32),
        nullable=True,
    )
