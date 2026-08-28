"""add multi role assignments

Revision ID: 8c42d0f319b7
Revises: 7b31c9e228a4
Create Date: 2026-08-28 04:15:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "8c42d0f319b7"
down_revision: str | Sequence[str] | None = "7b31c9e228a4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_roles",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role_code", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["role_code"], ["roles.code"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "role_code"),
    )
    op.execute(
        sa.text(
            "INSERT INTO user_roles (user_id, role_code) "
            "SELECT id, role FROM users"
        )
    )


def downgrade() -> None:
    op.drop_table("user_roles")
