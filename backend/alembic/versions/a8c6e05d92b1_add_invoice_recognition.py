"""add invoice recognition

Revision ID: a8c6e05d92b1
Revises: e63b4d92a817
Create Date: 2026-08-29 09:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a8c6e05d92b1"
down_revision: str | Sequence[str] | None = "e63b4d92a817"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "reimbursements",
        sa.Column("entity_name", sa.String(length=160), server_default="", nullable=False),
    )
    op.add_column(
        "reimbursements",
        sa.Column("tax_number", sa.String(length=32), server_default="", nullable=False),
    )
    op.add_column(
        "reimbursement_attachments",
        sa.Column("document_type", sa.String(length=24), server_default="voucher", nullable=False),
    )
    op.create_index(
        "ix_reimbursement_attachments_document_type",
        "reimbursement_attachments",
        ["document_type"],
    )

    op.create_table(
        "reimbursement_entities",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("tax_number", sa.String(length=32), nullable=False),
        sa.Column("is_default", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index("ix_reimbursement_entities_tax_number", "reimbursement_entities", ["tax_number"])
    op.create_index("ix_reimbursement_entities_is_active", "reimbursement_entities", ["is_active"])

    op.create_table(
        "reimbursement_invoices",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("attachment_id", sa.Integer(), nullable=False),
        sa.Column("recognition_status", sa.String(length=24), nullable=False),
        sa.Column("recognition_provider", sa.String(length=32), nullable=False),
        sa.Column("recognition_message", sa.String(length=500), nullable=True),
        sa.Column("recognized_entity_name", sa.String(length=160), nullable=True),
        sa.Column("recognized_tax_number", sa.String(length=32), nullable=True),
        sa.Column("recognized_amount", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("final_entity_name", sa.String(length=160), nullable=True),
        sa.Column("final_tax_number", sa.String(length=32), nullable=True),
        sa.Column("final_amount", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("invoice_code", sa.String(length=40), nullable=True),
        sa.Column("invoice_number", sa.String(length=40), nullable=True),
        sa.Column("invoice_date", sa.Date(), nullable=True),
        sa.Column("manually_edited", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("provider_request_id", sa.String(length=80), nullable=True),
        sa.Column("recognized_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["attachment_id"],
            ["reimbursement_attachments.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("attachment_id"),
    )
    op.create_index(
        "ix_reimbursement_invoices_attachment_id",
        "reimbursement_invoices",
        ["attachment_id"],
        unique=True,
    )
    op.create_index(
        "ix_reimbursement_invoices_recognition_status",
        "reimbursement_invoices",
        ["recognition_status"],
    )
    op.create_index("ix_reimbursement_invoices_invoice_code", "reimbursement_invoices", ["invoice_code"])
    op.create_index(
        "ix_reimbursement_invoices_invoice_number",
        "reimbursement_invoices",
        ["invoice_number"],
    )


def downgrade() -> None:
    op.drop_index("ix_reimbursement_invoices_invoice_number", table_name="reimbursement_invoices")
    op.drop_index("ix_reimbursement_invoices_invoice_code", table_name="reimbursement_invoices")
    op.drop_index(
        "ix_reimbursement_invoices_recognition_status",
        table_name="reimbursement_invoices",
    )
    op.drop_index("ix_reimbursement_invoices_attachment_id", table_name="reimbursement_invoices")
    op.drop_table("reimbursement_invoices")
    op.drop_index("ix_reimbursement_entities_is_active", table_name="reimbursement_entities")
    op.drop_index("ix_reimbursement_entities_tax_number", table_name="reimbursement_entities")
    op.drop_table("reimbursement_entities")
    op.drop_index(
        "ix_reimbursement_attachments_document_type",
        table_name="reimbursement_attachments",
    )
    op.drop_column("reimbursement_attachments", "document_type")
    op.drop_column("reimbursements", "tax_number")
    op.drop_column("reimbursements", "entity_name")
