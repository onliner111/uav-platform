"""phase18 wp3 report template export enforce

Revision ID: 202602260079
Revises: 202602260078
Create Date: 2026-02-26
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "202602260079"
down_revision = "202602260078"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_outcome_report_templates_format_default",
        "outcome_report_templates",
        "format_default IN ('PDF', 'WORD')",
    )
    op.create_check_constraint(
        "ck_outcome_report_templates_name_not_empty",
        "outcome_report_templates",
        "name <> ''",
    )
    op.create_check_constraint(
        "ck_outcome_report_exports_report_format",
        "outcome_report_exports",
        "report_format IN ('PDF', 'WORD')",
    )
    op.create_check_constraint(
        "ck_outcome_report_exports_status",
        "outcome_report_exports",
        "status IN ('RUNNING', 'SUCCEEDED', 'FAILED')",
    )
    op.create_check_constraint(
        "ck_outcome_report_exports_detail_is_object",
        "outcome_report_exports",
        "json_typeof(detail) = 'object'",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_outcome_report_exports_detail_is_object",
        "outcome_report_exports",
        type_="check",
    )
    op.drop_constraint(
        "ck_outcome_report_exports_status",
        "outcome_report_exports",
        type_="check",
    )
    op.drop_constraint(
        "ck_outcome_report_exports_report_format",
        "outcome_report_exports",
        type_="check",
    )
    op.drop_constraint(
        "ck_outcome_report_templates_name_not_empty",
        "outcome_report_templates",
        type_="check",
    )
    op.drop_constraint(
        "ck_outcome_report_templates_format_default",
        "outcome_report_templates",
        type_="check",
    )
