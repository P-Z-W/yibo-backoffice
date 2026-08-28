"""add analytics detail imports

Revision ID: d14a7c8e6f20
Revises: c82f19d46ab0
Create Date: 2026-08-28 09:30:00

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d14a7c8e6f20"
down_revision: str | Sequence[str] | None = "c82f19d46ab0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "analytics_import_batches",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("dataset_type", sa.String(length=50), nullable=False),
        sa.Column("month", sa.Date(), nullable=False),
        sa.Column("original_name", sa.String(length=255), nullable=False),
        sa.Column("sheet_name", sa.String(length=100), nullable=False),
        sa.Column("mode", sa.String(length=20), nullable=False),
        sa.Column("columns", sa.JSON(), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_analytics_import_batches_active",
        "analytics_import_batches",
        ["active"],
        unique=False,
    )
    op.create_index(
        "ix_analytics_import_batches_created_by_id",
        "analytics_import_batches",
        ["created_by_id"],
        unique=False,
    )
    op.create_index(
        "ix_analytics_import_batches_dataset_type",
        "analytics_import_batches",
        ["dataset_type"],
        unique=False,
    )
    op.create_index(
        "ix_analytics_import_batches_month",
        "analytics_import_batches",
        ["month"],
        unique=False,
    )
    op.create_index(
        "ix_analytics_import_dataset_month",
        "analytics_import_batches",
        ["dataset_type", "month", "active"],
        unique=False,
    )
    op.create_table(
        "analytics_detail_rows",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("batch_id", sa.Integer(), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["batch_id"], ["analytics_import_batches.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_analytics_detail_rows_batch_id",
        "analytics_detail_rows",
        ["batch_id"],
        unique=False,
    )
    op.create_index(
        "ix_analytics_detail_batch_row",
        "analytics_detail_rows",
        ["batch_id", "row_number"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_analytics_detail_batch_row", table_name="analytics_detail_rows")
    op.drop_index("ix_analytics_detail_rows_batch_id", table_name="analytics_detail_rows")
    op.drop_table("analytics_detail_rows")
    op.drop_index("ix_analytics_import_dataset_month", table_name="analytics_import_batches")
    op.drop_index("ix_analytics_import_batches_month", table_name="analytics_import_batches")
    op.drop_index(
        "ix_analytics_import_batches_dataset_type", table_name="analytics_import_batches"
    )
    op.drop_index(
        "ix_analytics_import_batches_created_by_id", table_name="analytics_import_batches"
    )
    op.drop_index("ix_analytics_import_batches_active", table_name="analytics_import_batches")
    op.drop_table("analytics_import_batches")
