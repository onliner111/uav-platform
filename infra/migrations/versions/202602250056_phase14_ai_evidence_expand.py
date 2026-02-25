"""phase14 ai evidence expand

Revision ID: 202602250056
Revises: 202602250055
Create Date: 2026-02-25
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "202602250056"
down_revision = "202602250055"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_analysis_jobs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("task_id", sa.String(), nullable=True),
        sa.Column("mission_id", sa.String(), nullable=True),
        sa.Column("topic", sa.String(length=120), nullable=True),
        sa.Column("job_type", sa.String(length=20), nullable=False),
        sa.Column("trigger_mode", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("model_provider", sa.String(length=80), nullable=False),
        sa.Column("model_name", sa.String(length=120), nullable=False),
        sa.Column("model_version", sa.String(length=120), nullable=False),
        sa.Column("threshold_config", sa.JSON(), nullable=False),
        sa.Column("input_config", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["inspection_tasks.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["mission_id"], ["missions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_ai_analysis_jobs_tenant_id_id"),
    )
    op.create_index("ix_ai_analysis_jobs_tenant_id", "ai_analysis_jobs", ["tenant_id"])
    op.create_index("ix_ai_analysis_jobs_task_id", "ai_analysis_jobs", ["task_id"])
    op.create_index("ix_ai_analysis_jobs_mission_id", "ai_analysis_jobs", ["mission_id"])
    op.create_index("ix_ai_analysis_jobs_topic", "ai_analysis_jobs", ["topic"])
    op.create_index("ix_ai_analysis_jobs_job_type", "ai_analysis_jobs", ["job_type"])
    op.create_index("ix_ai_analysis_jobs_trigger_mode", "ai_analysis_jobs", ["trigger_mode"])
    op.create_index("ix_ai_analysis_jobs_status", "ai_analysis_jobs", ["status"])
    op.create_index("ix_ai_analysis_jobs_created_by", "ai_analysis_jobs", ["created_by"])
    op.create_index("ix_ai_analysis_jobs_created_at", "ai_analysis_jobs", ["created_at"])
    op.create_index("ix_ai_analysis_jobs_updated_at", "ai_analysis_jobs", ["updated_at"])
    op.create_index("ix_ai_analysis_jobs_tenant_id_id", "ai_analysis_jobs", ["tenant_id", "id"])
    op.create_index("ix_ai_analysis_jobs_tenant_task", "ai_analysis_jobs", ["tenant_id", "task_id"])
    op.create_index(
        "ix_ai_analysis_jobs_tenant_mission",
        "ai_analysis_jobs",
        ["tenant_id", "mission_id"],
    )
    op.create_index("ix_ai_analysis_jobs_tenant_topic", "ai_analysis_jobs", ["tenant_id", "topic"])
    op.create_index("ix_ai_analysis_jobs_tenant_type", "ai_analysis_jobs", ["tenant_id", "job_type"])
    op.create_index("ix_ai_analysis_jobs_tenant_status", "ai_analysis_jobs", ["tenant_id", "status"])

    op.create_table(
        "ai_analysis_runs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("job_id", sa.String(), nullable=False),
        sa.Column("retry_of_run_id", sa.String(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("trigger_mode", sa.String(length=20), nullable=False),
        sa.Column("input_hash", sa.String(length=200), nullable=True),
        sa.Column("output_hash", sa.String(length=200), nullable=True),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("triggered_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["ai_analysis_jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["retry_of_run_id"], ["ai_analysis_runs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_ai_analysis_runs_tenant_id_id"),
    )
    op.create_index("ix_ai_analysis_runs_tenant_id", "ai_analysis_runs", ["tenant_id"])
    op.create_index("ix_ai_analysis_runs_job_id", "ai_analysis_runs", ["job_id"])
    op.create_index("ix_ai_analysis_runs_retry_of_run_id", "ai_analysis_runs", ["retry_of_run_id"])
    op.create_index("ix_ai_analysis_runs_status", "ai_analysis_runs", ["status"])
    op.create_index("ix_ai_analysis_runs_trigger_mode", "ai_analysis_runs", ["trigger_mode"])
    op.create_index("ix_ai_analysis_runs_input_hash", "ai_analysis_runs", ["input_hash"])
    op.create_index("ix_ai_analysis_runs_output_hash", "ai_analysis_runs", ["output_hash"])
    op.create_index("ix_ai_analysis_runs_triggered_by", "ai_analysis_runs", ["triggered_by"])
    op.create_index("ix_ai_analysis_runs_started_at", "ai_analysis_runs", ["started_at"])
    op.create_index("ix_ai_analysis_runs_finished_at", "ai_analysis_runs", ["finished_at"])
    op.create_index("ix_ai_analysis_runs_created_at", "ai_analysis_runs", ["created_at"])
    op.create_index("ix_ai_analysis_runs_updated_at", "ai_analysis_runs", ["updated_at"])
    op.create_index("ix_ai_analysis_runs_tenant_id_id", "ai_analysis_runs", ["tenant_id", "id"])
    op.create_index("ix_ai_analysis_runs_tenant_job", "ai_analysis_runs", ["tenant_id", "job_id"])
    op.create_index(
        "ix_ai_analysis_runs_tenant_status",
        "ai_analysis_runs",
        ["tenant_id", "status"],
    )
    op.create_index(
        "ix_ai_analysis_runs_tenant_retry_of",
        "ai_analysis_runs",
        ["tenant_id", "retry_of_run_id"],
    )

    op.create_table(
        "ai_analysis_outputs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("job_id", sa.String(), nullable=False),
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("summary_text", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("suggestion_text", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("control_allowed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("review_status", sa.String(length=20), nullable=False),
        sa.Column("reviewed_by", sa.String(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("override_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["ai_analysis_jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["ai_analysis_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_ai_analysis_outputs_tenant_id_id"),
    )
    op.create_index("ix_ai_analysis_outputs_tenant_id", "ai_analysis_outputs", ["tenant_id"])
    op.create_index("ix_ai_analysis_outputs_job_id", "ai_analysis_outputs", ["job_id"])
    op.create_index("ix_ai_analysis_outputs_run_id", "ai_analysis_outputs", ["run_id"])
    op.create_index("ix_ai_analysis_outputs_control_allowed", "ai_analysis_outputs", ["control_allowed"])
    op.create_index("ix_ai_analysis_outputs_review_status", "ai_analysis_outputs", ["review_status"])
    op.create_index("ix_ai_analysis_outputs_reviewed_by", "ai_analysis_outputs", ["reviewed_by"])
    op.create_index("ix_ai_analysis_outputs_reviewed_at", "ai_analysis_outputs", ["reviewed_at"])
    op.create_index("ix_ai_analysis_outputs_created_at", "ai_analysis_outputs", ["created_at"])
    op.create_index("ix_ai_analysis_outputs_updated_at", "ai_analysis_outputs", ["updated_at"])
    op.create_index("ix_ai_analysis_outputs_tenant_id_id", "ai_analysis_outputs", ["tenant_id", "id"])
    op.create_index("ix_ai_analysis_outputs_tenant_job", "ai_analysis_outputs", ["tenant_id", "job_id"])
    op.create_index("ix_ai_analysis_outputs_tenant_run", "ai_analysis_outputs", ["tenant_id", "run_id"])
    op.create_index(
        "ix_ai_analysis_outputs_tenant_review",
        "ai_analysis_outputs",
        ["tenant_id", "review_status"],
    )

    op.create_table(
        "ai_evidence_records",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("output_id", sa.String(), nullable=True),
        sa.Column("evidence_type", sa.String(length=30), nullable=False),
        sa.Column("content_hash", sa.String(length=200), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["ai_analysis_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["output_id"], ["ai_analysis_outputs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_ai_evidence_records_tenant_id_id"),
    )
    op.create_index("ix_ai_evidence_records_tenant_id", "ai_evidence_records", ["tenant_id"])
    op.create_index("ix_ai_evidence_records_run_id", "ai_evidence_records", ["run_id"])
    op.create_index("ix_ai_evidence_records_output_id", "ai_evidence_records", ["output_id"])
    op.create_index("ix_ai_evidence_records_evidence_type", "ai_evidence_records", ["evidence_type"])
    op.create_index("ix_ai_evidence_records_content_hash", "ai_evidence_records", ["content_hash"])
    op.create_index("ix_ai_evidence_records_created_at", "ai_evidence_records", ["created_at"])
    op.create_index("ix_ai_evidence_records_tenant_id_id", "ai_evidence_records", ["tenant_id", "id"])
    op.create_index("ix_ai_evidence_records_tenant_run", "ai_evidence_records", ["tenant_id", "run_id"])
    op.create_index(
        "ix_ai_evidence_records_tenant_output",
        "ai_evidence_records",
        ["tenant_id", "output_id"],
    )
    op.create_index("ix_ai_evidence_records_tenant_type", "ai_evidence_records", ["tenant_id", "evidence_type"])

    op.create_table(
        "ai_output_review_actions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("output_id", sa.String(), nullable=False),
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("action_type", sa.String(length=20), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("actor_id", sa.String(), nullable=False),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["output_id"], ["ai_analysis_outputs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["ai_analysis_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_ai_output_review_actions_tenant_id_id"),
    )
    op.create_index("ix_ai_output_review_actions_tenant_id", "ai_output_review_actions", ["tenant_id"])
    op.create_index("ix_ai_output_review_actions_output_id", "ai_output_review_actions", ["output_id"])
    op.create_index("ix_ai_output_review_actions_run_id", "ai_output_review_actions", ["run_id"])
    op.create_index("ix_ai_output_review_actions_action_type", "ai_output_review_actions", ["action_type"])
    op.create_index("ix_ai_output_review_actions_actor_id", "ai_output_review_actions", ["actor_id"])
    op.create_index("ix_ai_output_review_actions_created_at", "ai_output_review_actions", ["created_at"])
    op.create_index(
        "ix_ai_output_review_actions_tenant_id_id",
        "ai_output_review_actions",
        ["tenant_id", "id"],
    )
    op.create_index(
        "ix_ai_output_review_actions_tenant_output",
        "ai_output_review_actions",
        ["tenant_id", "output_id"],
    )
    op.create_index("ix_ai_output_review_actions_tenant_run", "ai_output_review_actions", ["tenant_id", "run_id"])
    op.create_index(
        "ix_ai_output_review_actions_tenant_action",
        "ai_output_review_actions",
        ["tenant_id", "action_type"],
    )


def downgrade() -> None:
    op.drop_index("ix_ai_output_review_actions_tenant_action", table_name="ai_output_review_actions")
    op.drop_index("ix_ai_output_review_actions_tenant_run", table_name="ai_output_review_actions")
    op.drop_index("ix_ai_output_review_actions_tenant_output", table_name="ai_output_review_actions")
    op.drop_index("ix_ai_output_review_actions_tenant_id_id", table_name="ai_output_review_actions")
    op.drop_index("ix_ai_output_review_actions_created_at", table_name="ai_output_review_actions")
    op.drop_index("ix_ai_output_review_actions_actor_id", table_name="ai_output_review_actions")
    op.drop_index("ix_ai_output_review_actions_action_type", table_name="ai_output_review_actions")
    op.drop_index("ix_ai_output_review_actions_run_id", table_name="ai_output_review_actions")
    op.drop_index("ix_ai_output_review_actions_output_id", table_name="ai_output_review_actions")
    op.drop_index("ix_ai_output_review_actions_tenant_id", table_name="ai_output_review_actions")
    op.drop_table("ai_output_review_actions")

    op.drop_index("ix_ai_evidence_records_tenant_type", table_name="ai_evidence_records")
    op.drop_index("ix_ai_evidence_records_tenant_output", table_name="ai_evidence_records")
    op.drop_index("ix_ai_evidence_records_tenant_run", table_name="ai_evidence_records")
    op.drop_index("ix_ai_evidence_records_tenant_id_id", table_name="ai_evidence_records")
    op.drop_index("ix_ai_evidence_records_created_at", table_name="ai_evidence_records")
    op.drop_index("ix_ai_evidence_records_content_hash", table_name="ai_evidence_records")
    op.drop_index("ix_ai_evidence_records_evidence_type", table_name="ai_evidence_records")
    op.drop_index("ix_ai_evidence_records_output_id", table_name="ai_evidence_records")
    op.drop_index("ix_ai_evidence_records_run_id", table_name="ai_evidence_records")
    op.drop_index("ix_ai_evidence_records_tenant_id", table_name="ai_evidence_records")
    op.drop_table("ai_evidence_records")

    op.drop_index("ix_ai_analysis_outputs_tenant_review", table_name="ai_analysis_outputs")
    op.drop_index("ix_ai_analysis_outputs_tenant_run", table_name="ai_analysis_outputs")
    op.drop_index("ix_ai_analysis_outputs_tenant_job", table_name="ai_analysis_outputs")
    op.drop_index("ix_ai_analysis_outputs_tenant_id_id", table_name="ai_analysis_outputs")
    op.drop_index("ix_ai_analysis_outputs_updated_at", table_name="ai_analysis_outputs")
    op.drop_index("ix_ai_analysis_outputs_created_at", table_name="ai_analysis_outputs")
    op.drop_index("ix_ai_analysis_outputs_reviewed_at", table_name="ai_analysis_outputs")
    op.drop_index("ix_ai_analysis_outputs_reviewed_by", table_name="ai_analysis_outputs")
    op.drop_index("ix_ai_analysis_outputs_review_status", table_name="ai_analysis_outputs")
    op.drop_index("ix_ai_analysis_outputs_control_allowed", table_name="ai_analysis_outputs")
    op.drop_index("ix_ai_analysis_outputs_run_id", table_name="ai_analysis_outputs")
    op.drop_index("ix_ai_analysis_outputs_job_id", table_name="ai_analysis_outputs")
    op.drop_index("ix_ai_analysis_outputs_tenant_id", table_name="ai_analysis_outputs")
    op.drop_table("ai_analysis_outputs")

    op.drop_index("ix_ai_analysis_runs_tenant_retry_of", table_name="ai_analysis_runs")
    op.drop_index("ix_ai_analysis_runs_tenant_status", table_name="ai_analysis_runs")
    op.drop_index("ix_ai_analysis_runs_tenant_job", table_name="ai_analysis_runs")
    op.drop_index("ix_ai_analysis_runs_tenant_id_id", table_name="ai_analysis_runs")
    op.drop_index("ix_ai_analysis_runs_updated_at", table_name="ai_analysis_runs")
    op.drop_index("ix_ai_analysis_runs_created_at", table_name="ai_analysis_runs")
    op.drop_index("ix_ai_analysis_runs_finished_at", table_name="ai_analysis_runs")
    op.drop_index("ix_ai_analysis_runs_started_at", table_name="ai_analysis_runs")
    op.drop_index("ix_ai_analysis_runs_triggered_by", table_name="ai_analysis_runs")
    op.drop_index("ix_ai_analysis_runs_output_hash", table_name="ai_analysis_runs")
    op.drop_index("ix_ai_analysis_runs_input_hash", table_name="ai_analysis_runs")
    op.drop_index("ix_ai_analysis_runs_trigger_mode", table_name="ai_analysis_runs")
    op.drop_index("ix_ai_analysis_runs_status", table_name="ai_analysis_runs")
    op.drop_index("ix_ai_analysis_runs_retry_of_run_id", table_name="ai_analysis_runs")
    op.drop_index("ix_ai_analysis_runs_job_id", table_name="ai_analysis_runs")
    op.drop_index("ix_ai_analysis_runs_tenant_id", table_name="ai_analysis_runs")
    op.drop_table("ai_analysis_runs")

    op.drop_index("ix_ai_analysis_jobs_tenant_status", table_name="ai_analysis_jobs")
    op.drop_index("ix_ai_analysis_jobs_tenant_type", table_name="ai_analysis_jobs")
    op.drop_index("ix_ai_analysis_jobs_tenant_topic", table_name="ai_analysis_jobs")
    op.drop_index("ix_ai_analysis_jobs_tenant_mission", table_name="ai_analysis_jobs")
    op.drop_index("ix_ai_analysis_jobs_tenant_task", table_name="ai_analysis_jobs")
    op.drop_index("ix_ai_analysis_jobs_tenant_id_id", table_name="ai_analysis_jobs")
    op.drop_index("ix_ai_analysis_jobs_updated_at", table_name="ai_analysis_jobs")
    op.drop_index("ix_ai_analysis_jobs_created_at", table_name="ai_analysis_jobs")
    op.drop_index("ix_ai_analysis_jobs_created_by", table_name="ai_analysis_jobs")
    op.drop_index("ix_ai_analysis_jobs_status", table_name="ai_analysis_jobs")
    op.drop_index("ix_ai_analysis_jobs_trigger_mode", table_name="ai_analysis_jobs")
    op.drop_index("ix_ai_analysis_jobs_job_type", table_name="ai_analysis_jobs")
    op.drop_index("ix_ai_analysis_jobs_topic", table_name="ai_analysis_jobs")
    op.drop_index("ix_ai_analysis_jobs_mission_id", table_name="ai_analysis_jobs")
    op.drop_index("ix_ai_analysis_jobs_task_id", table_name="ai_analysis_jobs")
    op.drop_index("ix_ai_analysis_jobs_tenant_id", table_name="ai_analysis_jobs")
    op.drop_table("ai_analysis_jobs")
