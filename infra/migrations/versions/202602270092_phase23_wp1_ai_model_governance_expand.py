"""phase23 wp1 ai model governance expand

Revision ID: 202602270092
Revises: 202602270091
Create Date: 2026-02-27
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "202602270092"
down_revision = "202602270091"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_model_catalogs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("model_key", sa.String(length=200), nullable=False),
        sa.Column("provider", sa.String(length=80), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_ai_model_catalogs_tenant_id_id"),
        sa.UniqueConstraint("tenant_id", "model_key", name="uq_ai_model_catalogs_tenant_model_key"),
    )
    op.create_index("ix_ai_model_catalogs_tenant_id", "ai_model_catalogs", ["tenant_id"])
    op.create_index("ix_ai_model_catalogs_model_key", "ai_model_catalogs", ["model_key"])
    op.create_index("ix_ai_model_catalogs_provider", "ai_model_catalogs", ["provider"])
    op.create_index("ix_ai_model_catalogs_display_name", "ai_model_catalogs", ["display_name"])
    op.create_index("ix_ai_model_catalogs_is_active", "ai_model_catalogs", ["is_active"])
    op.create_index("ix_ai_model_catalogs_created_by", "ai_model_catalogs", ["created_by"])
    op.create_index("ix_ai_model_catalogs_created_at", "ai_model_catalogs", ["created_at"])
    op.create_index("ix_ai_model_catalogs_updated_at", "ai_model_catalogs", ["updated_at"])
    op.create_index("ix_ai_model_catalogs_tenant_id_id", "ai_model_catalogs", ["tenant_id", "id"])
    op.create_index("ix_ai_model_catalogs_tenant_model_key", "ai_model_catalogs", ["tenant_id", "model_key"])
    op.create_index("ix_ai_model_catalogs_tenant_provider", "ai_model_catalogs", ["tenant_id", "provider"])
    op.create_index("ix_ai_model_catalogs_tenant_active", "ai_model_catalogs", ["tenant_id", "is_active"])

    op.create_table(
        "ai_model_versions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("model_id", sa.String(), nullable=False),
        sa.Column("version", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("artifact_ref", sa.String(length=500), nullable=True),
        sa.Column("threshold_defaults", sa.JSON(), nullable=False),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("promoted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["model_id"], ["ai_model_catalogs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_ai_model_versions_tenant_id_id"),
        sa.UniqueConstraint(
            "tenant_id",
            "model_id",
            "version",
            name="uq_ai_model_versions_tenant_model_version",
        ),
    )
    op.create_index("ix_ai_model_versions_tenant_id", "ai_model_versions", ["tenant_id"])
    op.create_index("ix_ai_model_versions_model_id", "ai_model_versions", ["model_id"])
    op.create_index("ix_ai_model_versions_version", "ai_model_versions", ["version"])
    op.create_index("ix_ai_model_versions_status", "ai_model_versions", ["status"])
    op.create_index("ix_ai_model_versions_created_by", "ai_model_versions", ["created_by"])
    op.create_index("ix_ai_model_versions_promoted_at", "ai_model_versions", ["promoted_at"])
    op.create_index("ix_ai_model_versions_created_at", "ai_model_versions", ["created_at"])
    op.create_index("ix_ai_model_versions_updated_at", "ai_model_versions", ["updated_at"])
    op.create_index("ix_ai_model_versions_tenant_id_id", "ai_model_versions", ["tenant_id", "id"])
    op.create_index("ix_ai_model_versions_tenant_model", "ai_model_versions", ["tenant_id", "model_id"])
    op.create_index(
        "ix_ai_model_versions_tenant_model_version",
        "ai_model_versions",
        ["tenant_id", "model_id", "version"],
    )
    op.create_index("ix_ai_model_versions_tenant_status", "ai_model_versions", ["tenant_id", "status"])

    op.create_table(
        "ai_model_rollout_policies",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("model_id", sa.String(), nullable=False),
        sa.Column("default_version_id", sa.String(), nullable=True),
        sa.Column("traffic_allocation", sa.JSON(), nullable=False),
        sa.Column("threshold_overrides", sa.JSON(), nullable=False),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("updated_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["model_id"], ["ai_model_catalogs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["default_version_id"], ["ai_model_versions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_ai_model_rollout_policies_tenant_id_id"),
        sa.UniqueConstraint("tenant_id", "model_id", name="uq_ai_model_rollout_policies_tenant_model"),
    )
    op.create_index("ix_ai_model_rollout_policies_tenant_id", "ai_model_rollout_policies", ["tenant_id"])
    op.create_index("ix_ai_model_rollout_policies_model_id", "ai_model_rollout_policies", ["model_id"])
    op.create_index(
        "ix_ai_model_rollout_policies_default_version_id",
        "ai_model_rollout_policies",
        ["default_version_id"],
    )
    op.create_index("ix_ai_model_rollout_policies_is_active", "ai_model_rollout_policies", ["is_active"])
    op.create_index("ix_ai_model_rollout_policies_updated_by", "ai_model_rollout_policies", ["updated_by"])
    op.create_index("ix_ai_model_rollout_policies_created_at", "ai_model_rollout_policies", ["created_at"])
    op.create_index("ix_ai_model_rollout_policies_updated_at", "ai_model_rollout_policies", ["updated_at"])
    op.create_index(
        "ix_ai_model_rollout_policies_tenant_id_id",
        "ai_model_rollout_policies",
        ["tenant_id", "id"],
    )
    op.create_index(
        "ix_ai_model_rollout_policies_tenant_model",
        "ai_model_rollout_policies",
        ["tenant_id", "model_id"],
    )
    op.create_index(
        "ix_ai_model_rollout_policies_tenant_active",
        "ai_model_rollout_policies",
        ["tenant_id", "is_active"],
    )

    op.add_column("ai_analysis_jobs", sa.Column("model_version_id", sa.String(), nullable=True))
    op.create_index("ix_ai_analysis_jobs_model_version_id", "ai_analysis_jobs", ["model_version_id"])
    op.create_index(
        "ix_ai_analysis_jobs_tenant_model_version",
        "ai_analysis_jobs",
        ["tenant_id", "model_version_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_ai_analysis_jobs_tenant_model_version", table_name="ai_analysis_jobs")
    op.drop_index("ix_ai_analysis_jobs_model_version_id", table_name="ai_analysis_jobs")
    op.drop_column("ai_analysis_jobs", "model_version_id")

    op.drop_index(
        "ix_ai_model_rollout_policies_tenant_active",
        table_name="ai_model_rollout_policies",
    )
    op.drop_index(
        "ix_ai_model_rollout_policies_tenant_model",
        table_name="ai_model_rollout_policies",
    )
    op.drop_index(
        "ix_ai_model_rollout_policies_tenant_id_id",
        table_name="ai_model_rollout_policies",
    )
    op.drop_index("ix_ai_model_rollout_policies_updated_at", table_name="ai_model_rollout_policies")
    op.drop_index("ix_ai_model_rollout_policies_created_at", table_name="ai_model_rollout_policies")
    op.drop_index("ix_ai_model_rollout_policies_updated_by", table_name="ai_model_rollout_policies")
    op.drop_index("ix_ai_model_rollout_policies_is_active", table_name="ai_model_rollout_policies")
    op.drop_index(
        "ix_ai_model_rollout_policies_default_version_id",
        table_name="ai_model_rollout_policies",
    )
    op.drop_index("ix_ai_model_rollout_policies_model_id", table_name="ai_model_rollout_policies")
    op.drop_index("ix_ai_model_rollout_policies_tenant_id", table_name="ai_model_rollout_policies")
    op.drop_table("ai_model_rollout_policies")

    op.drop_index("ix_ai_model_versions_tenant_status", table_name="ai_model_versions")
    op.drop_index("ix_ai_model_versions_tenant_model_version", table_name="ai_model_versions")
    op.drop_index("ix_ai_model_versions_tenant_model", table_name="ai_model_versions")
    op.drop_index("ix_ai_model_versions_tenant_id_id", table_name="ai_model_versions")
    op.drop_index("ix_ai_model_versions_updated_at", table_name="ai_model_versions")
    op.drop_index("ix_ai_model_versions_created_at", table_name="ai_model_versions")
    op.drop_index("ix_ai_model_versions_promoted_at", table_name="ai_model_versions")
    op.drop_index("ix_ai_model_versions_created_by", table_name="ai_model_versions")
    op.drop_index("ix_ai_model_versions_status", table_name="ai_model_versions")
    op.drop_index("ix_ai_model_versions_version", table_name="ai_model_versions")
    op.drop_index("ix_ai_model_versions_model_id", table_name="ai_model_versions")
    op.drop_index("ix_ai_model_versions_tenant_id", table_name="ai_model_versions")
    op.drop_table("ai_model_versions")

    op.drop_index("ix_ai_model_catalogs_tenant_active", table_name="ai_model_catalogs")
    op.drop_index("ix_ai_model_catalogs_tenant_provider", table_name="ai_model_catalogs")
    op.drop_index("ix_ai_model_catalogs_tenant_model_key", table_name="ai_model_catalogs")
    op.drop_index("ix_ai_model_catalogs_tenant_id_id", table_name="ai_model_catalogs")
    op.drop_index("ix_ai_model_catalogs_updated_at", table_name="ai_model_catalogs")
    op.drop_index("ix_ai_model_catalogs_created_at", table_name="ai_model_catalogs")
    op.drop_index("ix_ai_model_catalogs_created_by", table_name="ai_model_catalogs")
    op.drop_index("ix_ai_model_catalogs_is_active", table_name="ai_model_catalogs")
    op.drop_index("ix_ai_model_catalogs_display_name", table_name="ai_model_catalogs")
    op.drop_index("ix_ai_model_catalogs_provider", table_name="ai_model_catalogs")
    op.drop_index("ix_ai_model_catalogs_model_key", table_name="ai_model_catalogs")
    op.drop_index("ix_ai_model_catalogs_tenant_id", table_name="ai_model_catalogs")
    op.drop_table("ai_model_catalogs")
