"""add encrypted latest password

Revision ID: c82f19d46ab0
Revises: b71e04ac25fa
Create Date: 2026-08-28 12:25:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c82f19d46ab0"
down_revision: str | Sequence[str] | None = "b71e04ac25fa"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("latest_password_ciphertext", sa.String(length=512), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "latest_password_ciphertext")
