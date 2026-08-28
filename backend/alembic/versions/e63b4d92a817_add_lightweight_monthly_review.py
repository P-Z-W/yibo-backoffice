"""add lightweight monthly review workflow

Revision ID: e63b4d92a817
Revises: f2a6c91d7e30
Create Date: 2026-08-28 16:20:00

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e63b4d92a817"
down_revision: str | Sequence[str] | None = "f2a6c91d7e30"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "monthly_metrics",
        sa.Column(
            "source_type",
            sa.String(length=24),
            server_default="migration",
            nullable=False,
        ),
    )
    op.add_column(
        "monthly_metrics", sa.Column("source_name", sa.String(length=255), nullable=True)
    )
    op.add_column(
        "monthly_metrics", sa.Column("source_batch_id", sa.Integer(), nullable=True)
    )
    op.add_column(
        "monthly_metrics", sa.Column("updated_by_id", sa.Integer(), nullable=True)
    )
    op.create_index(
        "ix_monthly_metrics_source_type", "monthly_metrics", ["source_type"], unique=False
    )
    op.create_index(
        "ix_monthly_metrics_source_batch_id",
        "monthly_metrics",
        ["source_batch_id"],
        unique=False,
    )
    op.create_index(
        "ix_monthly_metrics_updated_by_id",
        "monthly_metrics",
        ["updated_by_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_monthly_metrics_source_batch",
        "monthly_metrics",
        "analytics_import_batches",
        ["source_batch_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_monthly_metrics_updated_by",
        "monthly_metrics",
        "users",
        ["updated_by_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column("monthly_reviews", sa.Column("highlights", sa.Text(), nullable=True))
    op.add_column("monthly_reviews", sa.Column("issues", sa.Text(), nullable=True))
    op.add_column("monthly_reviews", sa.Column("risks", sa.Text(), nullable=True))
    op.add_column("monthly_reviews", sa.Column("next_plan", sa.Text(), nullable=True))
    op.add_column("monthly_reviews", sa.Column("completed_at", sa.DateTime(), nullable=True))
    op.add_column("monthly_reviews", sa.Column("archived_at", sa.DateTime(), nullable=True))
    op.add_column("monthly_reviews", sa.Column("updated_by_id", sa.Integer(), nullable=True))
    op.create_index(
        "ix_monthly_reviews_updated_by_id",
        "monthly_reviews",
        ["updated_by_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_monthly_reviews_updated_by",
        "monthly_reviews",
        "users",
        ["updated_by_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_monthly_reviews_updated_by", "monthly_reviews", type_="foreignkey"
    )
    op.drop_index("ix_monthly_reviews_updated_by_id", table_name="monthly_reviews")
    op.drop_column("monthly_reviews", "updated_by_id")
    op.drop_column("monthly_reviews", "archived_at")
    op.drop_column("monthly_reviews", "completed_at")
    op.drop_column("monthly_reviews", "next_plan")
    op.drop_column("monthly_reviews", "risks")
    op.drop_column("monthly_reviews", "issues")
    op.drop_column("monthly_reviews", "highlights")

    op.drop_constraint(
        "fk_monthly_metrics_updated_by", "monthly_metrics", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_monthly_metrics_source_batch", "monthly_metrics", type_="foreignkey"
    )
    op.drop_index("ix_monthly_metrics_updated_by_id", table_name="monthly_metrics")
    op.drop_index("ix_monthly_metrics_source_batch_id", table_name="monthly_metrics")
    op.drop_index("ix_monthly_metrics_source_type", table_name="monthly_metrics")
    op.drop_column("monthly_metrics", "updated_by_id")
    op.drop_column("monthly_metrics", "source_batch_id")
    op.drop_column("monthly_metrics", "source_name")
    op.drop_column("monthly_metrics", "source_type")
