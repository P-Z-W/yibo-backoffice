"""add value-added service records

Revision ID: d6a8f3c21b47
Revises: c4f7a91e2d63
Create Date: 2026-08-31 14:55:00

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d6a8f3c21b47"
down_revision: str | Sequence[str] | None = "c4f7a91e2d63"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "value_added_records",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("month", sa.Date(), nullable=False),
        sa.Column("team_id", sa.String(length=80), server_default="", nullable=False),
        sa.Column("team_name", sa.String(length=160), server_default="", nullable=False),
        sa.Column("service_code", sa.String(length=80), server_default="", nullable=False),
        sa.Column("service_name", sa.String(length=160), server_default="", nullable=False),
        sa.Column("service_group", sa.String(length=100), server_default="", nullable=False),
        sa.Column("quantity", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_value_added_records_month", "value_added_records", ["month"])
    op.create_index(
        "ix_value_added_month_team", "value_added_records", ["month", "team_name"]
    )
    op.create_index(
        "ix_value_added_month_service",
        "value_added_records",
        ["month", "service_name"],
    )
    op.create_index(
        "ix_value_added_records_created_by_id",
        "value_added_records",
        ["created_by_id"],
    )
    op.create_index(
        "ix_value_added_records_updated_by_id",
        "value_added_records",
        ["updated_by_id"],
    )


def downgrade() -> None:
    op.drop_table("value_added_records")
