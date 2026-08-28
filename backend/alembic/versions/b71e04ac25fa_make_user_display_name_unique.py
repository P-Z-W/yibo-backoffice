"""make user display name unique

Revision ID: b71e04ac25fa
Revises: 8c42d0f319b7
Create Date: 2026-08-28 11:55:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "b71e04ac25fa"
down_revision: str | Sequence[str] | None = "8c42d0f319b7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint("uq_users_display_name", "users", ["display_name"])


def downgrade() -> None:
    op.drop_constraint("uq_users_display_name", "users", type_="unique")
