"""Initial portable report/job/budget schema."""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "analysis_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("cache_key", sa.String(200), nullable=True, unique=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
    )
    op.create_index("ix_analysis_jobs_status", "analysis_jobs", ["status"])
    op.create_table(
        "reports",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("payload", sa.Text(), nullable=False),
    )
    op.create_table(
        "request_budgets",
        sa.Column("key", sa.String(160), primary_key=True),
        sa.Column("used", sa.Integer(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("request_budgets")
    op.drop_table("reports")
    op.drop_index("ix_analysis_jobs_status", table_name="analysis_jobs")
    op.drop_table("analysis_jobs")
