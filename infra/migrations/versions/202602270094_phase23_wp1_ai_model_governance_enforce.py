"""phase23 wp1 ai model governance enforce

Revision ID: 202602270094
Revises: 202602270093
Create Date: 2026-02-27
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "202602270094"
down_revision = "202602270093"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("ai_analysis_jobs") as batch_op:
        batch_op.alter_column(
            "model_version_id",
            existing_type=sa.String(),
            nullable=False,
        )

    op.create_check_constraint(
        "ck_ai_model_versions_status",
        "ai_model_versions",
        "status IN ('DRAFT', 'CANARY', 'STABLE', 'DEPRECATED')",
    )
    op.create_check_constraint(
        "ck_ai_model_catalogs_model_key_not_empty",
        "ai_model_catalogs",
        "model_key <> ''",
    )
    op.create_check_constraint(
        "ck_ai_model_versions_version_not_empty",
        "ai_model_versions",
        "version <> ''",
    )
    op.create_check_constraint(
        "ck_ai_model_rollout_policies_default_version_not_empty",
        "ai_model_rollout_policies",
        "default_version_id IS NOT NULL",
    )

    op.create_foreign_key(
        "fk_ai_model_versions_tenant_model",
        "ai_model_versions",
        "ai_model_catalogs",
        ["tenant_id", "model_id"],
        ["tenant_id", "id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_ai_model_rollout_policies_tenant_model",
        "ai_model_rollout_policies",
        "ai_model_catalogs",
        ["tenant_id", "model_id"],
        ["tenant_id", "id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_ai_model_rollout_policies_tenant_default_version",
        "ai_model_rollout_policies",
        "ai_model_versions",
        ["tenant_id", "default_version_id"],
        ["tenant_id", "id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_ai_analysis_jobs_tenant_model_version",
        "ai_analysis_jobs",
        "ai_model_versions",
        ["tenant_id", "model_version_id"],
        ["tenant_id", "id"],
        ondelete="RESTRICT",
    )

    op.create_index(
        "uq_ai_model_versions_tenant_model_stable",
        "ai_model_versions",
        ["tenant_id", "model_id"],
        unique=True,
        postgresql_where=sa.text("status = 'STABLE'"),
        sqlite_where=sa.text("status = 'STABLE'"),
    )


def downgrade() -> None:
    op.drop_index("uq_ai_model_versions_tenant_model_stable", table_name="ai_model_versions")

    op.drop_constraint(
        "fk_ai_analysis_jobs_tenant_model_version",
        "ai_analysis_jobs",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_ai_model_rollout_policies_tenant_default_version",
        "ai_model_rollout_policies",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_ai_model_rollout_policies_tenant_model",
        "ai_model_rollout_policies",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_ai_model_versions_tenant_model",
        "ai_model_versions",
        type_="foreignkey",
    )

    op.drop_constraint(
        "ck_ai_model_rollout_policies_default_version_not_empty",
        "ai_model_rollout_policies",
        type_="check",
    )
    op.drop_constraint(
        "ck_ai_model_versions_version_not_empty",
        "ai_model_versions",
        type_="check",
    )
    op.drop_constraint(
        "ck_ai_model_catalogs_model_key_not_empty",
        "ai_model_catalogs",
        type_="check",
    )
    op.drop_constraint(
        "ck_ai_model_versions_status",
        "ai_model_versions",
        type_="check",
    )

    with op.batch_alter_table("ai_analysis_jobs") as batch_op:
        batch_op.alter_column(
            "model_version_id",
            existing_type=sa.String(),
            nullable=True,
        )
