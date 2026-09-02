"""add supplier management

Revision ID: b9d7c1e4a620
Revises: a8c6e05d92b1
Create Date: 2026-08-31 11:40:00

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b9d7c1e4a620"
down_revision: str | Sequence[str] | None = "a8c6e05d92b1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "suppliers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("normalized_name", sa.String(length=160), nullable=False),
        sa.Column("contact_name", sa.String(length=100), server_default="", nullable=False),
        sa.Column("contact_phone", sa.String(length=50), server_default="", nullable=False),
        sa.Column("address", sa.String(length=255), server_default="", nullable=False),
        sa.Column("cooperation_start_date", sa.Date(), nullable=True),
        sa.Column("product_types", sa.String(length=500), server_default="", nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("normalized_name", name="uq_suppliers_normalized_name"),
    )
    op.create_index("ix_suppliers_name", "suppliers", ["name"])
    op.create_index("ix_suppliers_is_active", "suppliers", ["is_active"])
    op.create_index("ix_suppliers_created_by_id", "suppliers", ["created_by_id"])
    op.create_index("ix_suppliers_updated_by_id", "suppliers", ["updated_by_id"])

    op.create_table(
        "supplier_changes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("supplier_id", sa.Integer(), nullable=False),
        sa.Column("change_month", sa.Date(), nullable=False),
        sa.Column("change_type", sa.String(length=24), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("change_note", sa.Text(), nullable=True),
        sa.Column("changed_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["changed_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_supplier_changes_supplier_id", "supplier_changes", ["supplier_id"])
    op.create_index("ix_supplier_changes_change_month", "supplier_changes", ["change_month"])
    op.create_index("ix_supplier_changes_change_type", "supplier_changes", ["change_type"])
    op.create_index("ix_supplier_changes_changed_by_id", "supplier_changes", ["changed_by_id"])
    op.create_index(
        "ix_supplier_changes_month_supplier",
        "supplier_changes",
        ["change_month", "supplier_id"],
    )
    op.create_index(
        "ix_supplier_changes_created_at", "supplier_changes", ["created_at"]
    )

    permissions = sa.table(
        "permissions",
        sa.column("code", sa.String),
        sa.column("name", sa.String),
        sa.column("module", sa.String),
        sa.column("action", sa.String),
        sa.column("sort_order", sa.Integer),
        sa.column("supports_scope", sa.Boolean),
    )
    op.bulk_insert(
        permissions,
        [
            {
                "code": "suppliers.view",
                "name": "查看供应商",
                "module": "供应商管理",
                "action": "查看",
                "sort_order": 72,
                "supports_scope": False,
            },
            {
                "code": "suppliers.manage",
                "name": "维护供应商",
                "module": "供应商管理",
                "action": "维护",
                "sort_order": 73,
                "supports_scope": False,
            },
        ],
    )
    role_permissions = sa.table(
        "role_permissions",
        sa.column("role_code", sa.String),
        sa.column("permission_code", sa.String),
        sa.column("data_scope", sa.String),
    )
    op.bulk_insert(
        role_permissions,
        [
            {"role_code": "admin", "permission_code": code, "data_scope": "all"}
            for code in ("suppliers.view", "suppliers.manage")
        ]
        + [
            {"role_code": "management", "permission_code": code, "data_scope": "all"}
            for code in ("suppliers.view", "suppliers.manage")
        ]
        + [
            {"role_code": role, "permission_code": "suppliers.view", "data_scope": "all"}
            for role in ("supervisor", "finance", "operator")
        ],
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM role_permissions "
            "WHERE permission_code IN ('suppliers.view', 'suppliers.manage')"
        )
    )
    op.execute(
        sa.text(
            "DELETE FROM permissions "
            "WHERE code IN ('suppliers.view', 'suppliers.manage')"
        )
    )
    op.drop_index("ix_supplier_changes_created_at", table_name="supplier_changes")
    op.drop_index("ix_supplier_changes_month_supplier", table_name="supplier_changes")
    op.drop_index("ix_supplier_changes_changed_by_id", table_name="supplier_changes")
    op.drop_index("ix_supplier_changes_change_type", table_name="supplier_changes")
    op.drop_index("ix_supplier_changes_change_month", table_name="supplier_changes")
    op.drop_index("ix_supplier_changes_supplier_id", table_name="supplier_changes")
    op.drop_table("supplier_changes")
    op.drop_index("ix_suppliers_updated_by_id", table_name="suppliers")
    op.drop_index("ix_suppliers_created_by_id", table_name="suppliers")
    op.drop_index("ix_suppliers_is_active", table_name="suppliers")
    op.drop_index("ix_suppliers_name", table_name="suppliers")
    op.drop_table("suppliers")
