"""phase14 ai evidence backfill validate

Revision ID: 202602250057
Revises: 202602250056
Create Date: 2026-02-25
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "202602250057"
down_revision = "202602250056"
branch_labels = None
depends_on = None


def _assert_zero(bind: sa.engine.Connection, sql: str, error_message: str) -> None:
    rows = list(bind.execute(sa.text(sql)))
    if rows:
        raise RuntimeError(f"{error_message}. count={len(rows)}")


def upgrade() -> None:
    bind = op.get_bind()
    _assert_zero(
        bind,
        """
        SELECT id FROM ai_analysis_jobs
        WHERE job_type NOT IN ('SUMMARY', 'SUGGESTION')
        """,
        "Phase14 validation failed: ai_analysis_jobs.job_type out of enum range",
    )
    _assert_zero(
        bind,
        """
        SELECT id FROM ai_analysis_jobs
        WHERE trigger_mode NOT IN ('MANUAL', 'SCHEDULED', 'NEAR_REALTIME')
        """,
        "Phase14 validation failed: ai_analysis_jobs.trigger_mode out of enum range",
    )
    _assert_zero(
        bind,
        """
        SELECT id FROM ai_analysis_jobs
        WHERE status NOT IN ('ACTIVE', 'PAUSED')
        """,
        "Phase14 validation failed: ai_analysis_jobs.status out of enum range",
    )
    _assert_zero(
        bind,
        """
        SELECT id FROM ai_analysis_runs
        WHERE status NOT IN ('RUNNING', 'SUCCEEDED', 'FAILED')
        """,
        "Phase14 validation failed: ai_analysis_runs.status out of enum range",
    )
    _assert_zero(
        bind,
        """
        SELECT id FROM ai_analysis_runs
        WHERE trigger_mode NOT IN ('MANUAL', 'SCHEDULED', 'NEAR_REALTIME')
        """,
        "Phase14 validation failed: ai_analysis_runs.trigger_mode out of enum range",
    )
    _assert_zero(
        bind,
        """
        SELECT id FROM ai_analysis_runs
        WHERE retry_count < 0
        """,
        "Phase14 validation failed: ai_analysis_runs.retry_count must be non-negative",
    )
    _assert_zero(
        bind,
        """
        SELECT id FROM ai_analysis_outputs
        WHERE review_status NOT IN ('PENDING_REVIEW', 'APPROVED', 'REJECTED', 'OVERRIDDEN')
        """,
        "Phase14 validation failed: ai_analysis_outputs.review_status out of enum range",
    )
    _assert_zero(
        bind,
        """
        SELECT id FROM ai_analysis_outputs
        WHERE control_allowed = true
        """,
        "Phase14 validation failed: ai_analysis_outputs.control_allowed must stay false",
    )
    _assert_zero(
        bind,
        """
        SELECT id FROM ai_evidence_records
        WHERE evidence_type NOT IN ('MODEL_CONFIG', 'INPUT_SNAPSHOT', 'OUTPUT_SNAPSHOT', 'TRACE')
        """,
        "Phase14 validation failed: ai_evidence_records.evidence_type out of enum range",
    )
    _assert_zero(
        bind,
        """
        SELECT id FROM ai_output_review_actions
        WHERE action_type NOT IN ('APPROVE', 'REJECT', 'OVERRIDE')
        """,
        "Phase14 validation failed: ai_output_review_actions.action_type out of enum range",
    )


def downgrade() -> None:
    # Validation-only step.
    pass
