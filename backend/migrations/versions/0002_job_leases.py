"""Add process-owned job leases for safe overlapping deployments."""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("analysis_jobs", sa.Column("owner_id", sa.String(36), nullable=True))
    op.add_column(
        "analysis_jobs", sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_index("ix_analysis_jobs_owner_id", "analysis_jobs", ["owner_id"])


def downgrade() -> None:
    op.drop_index("ix_analysis_jobs_owner_id", table_name="analysis_jobs")
    op.drop_column("analysis_jobs", "lease_expires_at")
    op.drop_column("analysis_jobs", "owner_id")
