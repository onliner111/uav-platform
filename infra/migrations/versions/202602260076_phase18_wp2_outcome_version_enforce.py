"""phase18 wp2 outcome version enforce

Revision ID: 202602260076
Revises: 202602260075
Create Date: 2026-02-26
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "202602260076"
down_revision = "202602260075"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_outcome_catalog_versions_version_no_positive",
        "outcome_catalog_versions",
        "version_no > 0",
    )
    op.create_check_constraint(
        "ck_outcome_catalog_versions_payload_is_object",
        "outcome_catalog_versions",
        "json_typeof(payload) = 'object'",
    )
    op.create_check_constraint(
        "ck_outcome_catalog_versions_change_type",
        "outcome_catalog_versions",
        "change_type IN ('INIT_SNAPSHOT', 'AUTO_MATERIALIZE', 'STATUS_UPDATE')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_outcome_catalog_versions_change_type",
        "outcome_catalog_versions",
        type_="check",
    )
    op.drop_constraint(
        "ck_outcome_catalog_versions_payload_is_object",
        "outcome_catalog_versions",
        type_="check",
    )
    op.drop_constraint(
        "ck_outcome_catalog_versions_version_no_positive",
        "outcome_catalog_versions",
        type_="check",
    )
