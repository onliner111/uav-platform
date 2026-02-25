"""phase14 ai evidence enforce

Revision ID: 202602250058
Revises: 202602250057
Create Date: 2026-02-25
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "202602250058"
down_revision = "202602250057"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_ai_analysis_jobs_job_type",
        "ai_analysis_jobs",
        "job_type IN ('SUMMARY', 'SUGGESTION')",
    )
    op.create_check_constraint(
        "ck_ai_analysis_jobs_trigger_mode",
        "ai_analysis_jobs",
        "trigger_mode IN ('MANUAL', 'SCHEDULED', 'NEAR_REALTIME')",
    )
    op.create_check_constraint(
        "ck_ai_analysis_jobs_status",
        "ai_analysis_jobs",
        "status IN ('ACTIVE', 'PAUSED')",
    )

    op.create_check_constraint(
        "ck_ai_analysis_runs_status",
        "ai_analysis_runs",
        "status IN ('RUNNING', 'SUCCEEDED', 'FAILED')",
    )
    op.create_check_constraint(
        "ck_ai_analysis_runs_trigger_mode",
        "ai_analysis_runs",
        "trigger_mode IN ('MANUAL', 'SCHEDULED', 'NEAR_REALTIME')",
    )
    op.create_check_constraint(
        "ck_ai_analysis_runs_retry_count",
        "ai_analysis_runs",
        "retry_count >= 0",
    )

    op.create_check_constraint(
        "ck_ai_analysis_outputs_review_status",
        "ai_analysis_outputs",
        "review_status IN ('PENDING_REVIEW', 'APPROVED', 'REJECTED', 'OVERRIDDEN')",
    )
    op.create_check_constraint(
        "ck_ai_analysis_outputs_control_allowed",
        "ai_analysis_outputs",
        "control_allowed = false",
    )

    op.create_check_constraint(
        "ck_ai_evidence_records_type",
        "ai_evidence_records",
        "evidence_type IN ('MODEL_CONFIG', 'INPUT_SNAPSHOT', 'OUTPUT_SNAPSHOT', 'TRACE')",
    )
    op.create_check_constraint(
        "ck_ai_output_review_actions_type",
        "ai_output_review_actions",
        "action_type IN ('APPROVE', 'REJECT', 'OVERRIDE')",
    )

    op.create_foreign_key(
        "fk_ai_analysis_runs_tenant_job",
        "ai_analysis_runs",
        "ai_analysis_jobs",
        ["tenant_id", "job_id"],
        ["tenant_id", "id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_ai_analysis_outputs_tenant_job",
        "ai_analysis_outputs",
        "ai_analysis_jobs",
        ["tenant_id", "job_id"],
        ["tenant_id", "id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_ai_analysis_outputs_tenant_run",
        "ai_analysis_outputs",
        "ai_analysis_runs",
        ["tenant_id", "run_id"],
        ["tenant_id", "id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_ai_evidence_records_tenant_run",
        "ai_evidence_records",
        "ai_analysis_runs",
        ["tenant_id", "run_id"],
        ["tenant_id", "id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_ai_evidence_records_tenant_output",
        "ai_evidence_records",
        "ai_analysis_outputs",
        ["tenant_id", "output_id"],
        ["tenant_id", "id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_ai_output_review_actions_tenant_output",
        "ai_output_review_actions",
        "ai_analysis_outputs",
        ["tenant_id", "output_id"],
        ["tenant_id", "id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_ai_output_review_actions_tenant_run",
        "ai_output_review_actions",
        "ai_analysis_runs",
        ["tenant_id", "run_id"],
        ["tenant_id", "id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_ai_output_review_actions_tenant_run",
        "ai_output_review_actions",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_ai_output_review_actions_tenant_output",
        "ai_output_review_actions",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_ai_evidence_records_tenant_output",
        "ai_evidence_records",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_ai_evidence_records_tenant_run",
        "ai_evidence_records",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_ai_analysis_outputs_tenant_run",
        "ai_analysis_outputs",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_ai_analysis_outputs_tenant_job",
        "ai_analysis_outputs",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_ai_analysis_runs_tenant_job",
        "ai_analysis_runs",
        type_="foreignkey",
    )

    op.drop_constraint(
        "ck_ai_output_review_actions_type",
        "ai_output_review_actions",
        type_="check",
    )
    op.drop_constraint(
        "ck_ai_evidence_records_type",
        "ai_evidence_records",
        type_="check",
    )
    op.drop_constraint(
        "ck_ai_analysis_outputs_control_allowed",
        "ai_analysis_outputs",
        type_="check",
    )
    op.drop_constraint(
        "ck_ai_analysis_outputs_review_status",
        "ai_analysis_outputs",
        type_="check",
    )
    op.drop_constraint(
        "ck_ai_analysis_runs_retry_count",
        "ai_analysis_runs",
        type_="check",
    )
    op.drop_constraint(
        "ck_ai_analysis_runs_trigger_mode",
        "ai_analysis_runs",
        type_="check",
    )
    op.drop_constraint(
        "ck_ai_analysis_runs_status",
        "ai_analysis_runs",
        type_="check",
    )
    op.drop_constraint(
        "ck_ai_analysis_jobs_status",
        "ai_analysis_jobs",
        type_="check",
    )
    op.drop_constraint(
        "ck_ai_analysis_jobs_trigger_mode",
        "ai_analysis_jobs",
        type_="check",
    )
    op.drop_constraint(
        "ck_ai_analysis_jobs_job_type",
        "ai_analysis_jobs",
        type_="check",
    )
