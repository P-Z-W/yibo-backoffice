"""store cloud customer occurrence timestamps

Revision ID: e7b4c29a61d0
Revises: d6a8f3c21b47
Create Date: 2026-09-02 16:30:00

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e7b4c29a61d0"
down_revision: str | Sequence[str] | None = "d6a8f3c21b47"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "customer_change_records",
        "month",
        existing_type=sa.Date(),
        nullable=True,
    )
    op.add_column(
        "customer_change_records",
        sa.Column("occurred_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "customer_change_records",
        sa.Column("source_team_id", sa.BigInteger(), nullable=True),
    )
    op.create_index(
        "ix_customer_change_occurred_at",
        "customer_change_records",
        ["occurred_at"],
    )
    op.create_index(
        "ux_customer_change_source_team",
        "customer_change_records",
        ["source_team_id"],
        unique=True,
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE customer_change_records "
            "SET month = DATE_FORMAT(occurred_at, '%Y-%m-01') "
            "WHERE month IS NULL AND occurred_at IS NOT NULL"
        )
    )
    op.drop_index("ux_customer_change_source_team", table_name="customer_change_records")
    op.drop_index("ix_customer_change_occurred_at", table_name="customer_change_records")
    op.drop_column("customer_change_records", "source_team_id")
    op.drop_column("customer_change_records", "occurred_at")
    op.alter_column(
        "customer_change_records",
        "month",
        existing_type=sa.Date(),
        nullable=False,
    )
