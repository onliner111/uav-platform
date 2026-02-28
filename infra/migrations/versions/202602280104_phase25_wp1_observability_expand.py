"""phase25 wp1 observability expand

Revision ID: 202602280104
Revises: 202602270103
Create Date: 2026-02-28
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "202602280104"
down_revision = "202602270103"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "observability_signals",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("signal_type", sa.String(length=20), nullable=False),
        sa.Column("level", sa.String(length=20), nullable=False),
        sa.Column("service_name", sa.String(length=120), nullable=False),
        sa.Column("signal_name", sa.String(length=120), nullable=False),
        sa.Column("trace_id", sa.String(length=120), nullable=True),
        sa.Column("span_id", sa.String(length=120), nullable=True),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("numeric_value", sa.Float(), nullable=True),
        sa.Column("unit", sa.String(length=40), nullable=True),
        sa.Column("message", sa.String(length=500), nullable=True),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_observability_signals_tenant_id_id"),
    )
    op.create_index("ix_observability_signals_tenant_id", "observability_signals", ["tenant_id"])
    op.create_index("ix_observability_signals_signal_type", "observability_signals", ["signal_type"])
    op.create_index("ix_observability_signals_level", "observability_signals", ["level"])
    op.create_index("ix_observability_signals_service_name", "observability_signals", ["service_name"])
    op.create_index("ix_observability_signals_signal_name", "observability_signals", ["signal_name"])
    op.create_index("ix_observability_signals_trace_id", "observability_signals", ["trace_id"])
    op.create_index("ix_observability_signals_span_id", "observability_signals", ["span_id"])
    op.create_index("ix_observability_signals_status_code", "observability_signals", ["status_code"])
    op.create_index("ix_observability_signals_duration_ms", "observability_signals", ["duration_ms"])
    op.create_index("ix_observability_signals_numeric_value", "observability_signals", ["numeric_value"])
    op.create_index("ix_observability_signals_created_by", "observability_signals", ["created_by"])
    op.create_index("ix_observability_signals_created_at", "observability_signals", ["created_at"])
    op.create_index(
        "ix_observability_signals_tenant_id_id",
        "observability_signals",
        ["tenant_id", "id"],
    )
    op.create_index(
        "ix_observability_signals_tenant_type",
        "observability_signals",
        ["tenant_id", "signal_type"],
    )
    op.create_index(
        "ix_observability_signals_tenant_service_ts",
        "observability_signals",
        ["tenant_id", "service_name", "created_at"],
    )
    op.create_index(
        "ix_observability_signals_tenant_trace",
        "observability_signals",
        ["tenant_id", "trace_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_observability_signals_tenant_trace", table_name="observability_signals")
    op.drop_index("ix_observability_signals_tenant_service_ts", table_name="observability_signals")
    op.drop_index("ix_observability_signals_tenant_type", table_name="observability_signals")
    op.drop_index("ix_observability_signals_tenant_id_id", table_name="observability_signals")
    op.drop_index("ix_observability_signals_created_at", table_name="observability_signals")
    op.drop_index("ix_observability_signals_created_by", table_name="observability_signals")
    op.drop_index("ix_observability_signals_numeric_value", table_name="observability_signals")
    op.drop_index("ix_observability_signals_duration_ms", table_name="observability_signals")
    op.drop_index("ix_observability_signals_status_code", table_name="observability_signals")
    op.drop_index("ix_observability_signals_span_id", table_name="observability_signals")
    op.drop_index("ix_observability_signals_trace_id", table_name="observability_signals")
    op.drop_index("ix_observability_signals_signal_name", table_name="observability_signals")
    op.drop_index("ix_observability_signals_service_name", table_name="observability_signals")
    op.drop_index("ix_observability_signals_level", table_name="observability_signals")
    op.drop_index("ix_observability_signals_signal_type", table_name="observability_signals")
    op.drop_index("ix_observability_signals_tenant_id", table_name="observability_signals")
    op.drop_table("observability_signals")
