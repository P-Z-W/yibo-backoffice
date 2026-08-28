"""add reimbursement workflow

Revision ID: 9f12a8d3b744
Revises: 4c40da42cc1b
Create Date: 2026-08-27 18:20:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "9f12a8d3b744"
down_revision: str | Sequence[str] | None = "4c40da42cc1b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users", sa.Column("team", sa.String(length=40), nullable=False, server_default="")
    )

    op.create_table(
        "reimbursements",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("number", sa.String(length=24), nullable=False),
        sa.Column("applicant_id", sa.Integer(), nullable=False),
        sa.Column("applicant_name", sa.String(length=80), nullable=False),
        sa.Column("team", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("total_amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("finance_approval_required", sa.Boolean(), nullable=False),
        sa.Column("exported", sa.Boolean(), nullable=False),
        sa.Column("export_batch", sa.String(length=40), nullable=True),
        sa.Column("submitted_at", sa.DateTime(), nullable=True),
        sa.Column("supervisor_approved_at", sa.DateTime(), nullable=True),
        sa.Column("finance_approved_at", sa.DateTime(), nullable=True),
        sa.Column("exported_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["applicant_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_reimbursements_applicant_id", "reimbursements", ["applicant_id"])
    op.create_index("ix_reimbursements_created_at", "reimbursements", ["created_at"])
    op.create_index("ix_reimbursements_exported", "reimbursements", ["exported"])
    op.create_index("ix_reimbursements_number", "reimbursements", ["number"], unique=True)
    op.create_index("ix_reimbursements_status", "reimbursements", ["status"])
    op.create_index("ix_reimbursements_team", "reimbursements", ["team"])
    op.create_index("ix_reimbursements_team_status", "reimbursements", ["team", "status"])

    op.create_table(
        "reimbursement_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("reimbursement_id", sa.Integer(), nullable=False),
        sa.Column("expense_date", sa.Date(), nullable=False),
        sa.Column("category", sa.String(length=60), nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("related_number", sa.String(length=100), nullable=True),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["reimbursement_id"], ["reimbursements.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_reimbursement_items_reimbursement_id", "reimbursement_items", ["reimbursement_id"]
    )
    op.create_index(
        "ix_reimbursement_items_related_number", "reimbursement_items", ["related_number"]
    )

    op.create_table(
        "reimbursement_attachments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("reimbursement_id", sa.Integer(), nullable=False),
        sa.Column("uploaded_by", sa.Integer(), nullable=False),
        sa.Column("original_name", sa.String(length=255), nullable=False),
        sa.Column("stored_name", sa.String(length=255), nullable=False),
        sa.Column("relative_path", sa.String(length=500), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["reimbursement_id"], ["reimbursements.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("relative_path"),
    )
    op.create_index(
        "ix_reimbursement_attachments_reimbursement_id",
        "reimbursement_attachments",
        ["reimbursement_id"],
    )
    op.create_index("ix_reimbursement_attachments_sha256", "reimbursement_attachments", ["sha256"])

    op.create_table(
        "reimbursement_approvals",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("reimbursement_id", sa.Integer(), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=False),
        sa.Column("actor_name", sa.String(length=80), nullable=False),
        sa.Column("actor_role", sa.String(length=32), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("from_status", sa.String(length=32), nullable=False),
        sa.Column("to_status", sa.String(length=32), nullable=False),
        sa.Column("comment", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["reimbursement_id"], ["reimbursements.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_reimbursement_approvals_reimbursement_id",
        "reimbursement_approvals",
        ["reimbursement_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_reimbursement_approvals_reimbursement_id", table_name="reimbursement_approvals"
    )
    op.drop_table("reimbursement_approvals")
    op.drop_index("ix_reimbursement_attachments_sha256", table_name="reimbursement_attachments")
    op.drop_index(
        "ix_reimbursement_attachments_reimbursement_id", table_name="reimbursement_attachments"
    )
    op.drop_table("reimbursement_attachments")
    op.drop_index("ix_reimbursement_items_related_number", table_name="reimbursement_items")
    op.drop_index("ix_reimbursement_items_reimbursement_id", table_name="reimbursement_items")
    op.drop_table("reimbursement_items")
    op.drop_index("ix_reimbursements_team_status", table_name="reimbursements")
    op.drop_index("ix_reimbursements_team", table_name="reimbursements")
    op.drop_index("ix_reimbursements_status", table_name="reimbursements")
    op.drop_index("ix_reimbursements_number", table_name="reimbursements")
    op.drop_index("ix_reimbursements_exported", table_name="reimbursements")
    op.drop_index("ix_reimbursements_created_at", table_name="reimbursements")
    op.drop_index("ix_reimbursements_applicant_id", table_name="reimbursements")
    op.drop_table("reimbursements")
    op.drop_column("users", "team")
