"""add customer, service and short-video record modules

Revision ID: c4f7a91e2d63
Revises: b9d7c1e4a620
Create Date: 2026-08-31 14:40:00

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c4f7a91e2d63"
down_revision: str | Sequence[str] | None = "b9d7c1e4a620"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def audit_columns() -> list[sa.Column]:
    return [
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
    ]


def audit_constraints() -> list[sa.ForeignKeyConstraint]:
    return [
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"], ondelete="SET NULL"),
    ]


def audit_indexes(table_name: str) -> None:
    op.create_index(f"ix_{table_name}_created_by_id", table_name, ["created_by_id"])
    op.create_index(f"ix_{table_name}_updated_by_id", table_name, ["updated_by_id"])


def upgrade() -> None:
    op.create_table(
        "customer_change_records",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("month", sa.Date(), nullable=False),
        sa.Column("change_type", sa.String(length=20), nullable=False),
        sa.Column("customer_name", sa.String(length=160), server_default="", nullable=False),
        sa.Column("source_channel", sa.String(length=100), server_default="", nullable=False),
        sa.Column("quantity", sa.Integer(), server_default="1", nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        *audit_columns(),
        *audit_constraints(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_customer_change_records_month", "customer_change_records", ["month"])
    op.create_index(
        "ix_customer_change_records_change_type",
        "customer_change_records",
        ["change_type"],
    )
    op.create_index(
        "ix_customer_change_month_type",
        "customer_change_records",
        ["month", "change_type"],
    )
    op.create_index(
        "ix_customer_change_month_customer",
        "customer_change_records",
        ["month", "customer_name"],
    )
    audit_indexes("customer_change_records")

    op.create_table(
        "customer_service_records",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("month", sa.Date(), nullable=False),
        sa.Column("team_name", sa.String(length=160), server_default="", nullable=False),
        sa.Column("complaint_category", sa.String(length=120), server_default="", nullable=False),
        sa.Column("issue_description", sa.Text(), nullable=False),
        sa.Column("verified_cause", sa.Text(), nullable=True),
        sa.Column("responsibility", sa.String(length=160), server_default="", nullable=False),
        sa.Column("corrective_action", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=30), server_default="待核实", nullable=False),
        *audit_columns(),
        *audit_constraints(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_customer_service_records_month", "customer_service_records", ["month"])
    op.create_index(
        "ix_customer_service_records_status", "customer_service_records", ["status"]
    )
    op.create_index(
        "ix_customer_service_month_status",
        "customer_service_records",
        ["month", "status"],
    )
    op.create_index(
        "ix_customer_service_month_team",
        "customer_service_records",
        ["month", "team_name"],
    )
    audit_indexes("customer_service_records")

    op.create_table(
        "short_video_records",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("month", sa.Date(), nullable=False),
        sa.Column("video_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("video_type", sa.String(length=120), server_default="", nullable=False),
        sa.Column("owner", sa.String(length=100), server_default="", nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        *audit_columns(),
        *audit_constraints(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_short_video_records_month", "short_video_records", ["month"])
    op.create_index(
        "ix_short_video_month_type", "short_video_records", ["month", "video_type"]
    )
    audit_indexes("short_video_records")

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
                "code": "operations_data.view",
                "name": "查看业务台账",
                "module": "客户与运营管理",
                "action": "查看",
                "sort_order": 74,
                "supports_scope": False,
            },
            {
                "code": "operations_data.manage",
                "name": "维护业务台账",
                "module": "客户与运营管理",
                "action": "维护",
                "sort_order": 75,
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
            {"role_code": role, "permission_code": code, "data_scope": "all"}
            for role in ("admin", "management")
            for code in ("operations_data.view", "operations_data.manage")
        ]
        + [
            {
                "role_code": role,
                "permission_code": "operations_data.view",
                "data_scope": "all",
            }
            for role in ("supervisor", "finance", "operator")
        ],
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM role_permissions WHERE permission_code IN "
            "('operations_data.view', 'operations_data.manage')"
        )
    )
    op.execute(
        sa.text(
            "DELETE FROM permissions WHERE code IN "
            "('operations_data.view', 'operations_data.manage')"
        )
    )
    for table_name in (
        "short_video_records",
        "customer_service_records",
        "customer_change_records",
    ):
        op.drop_table(table_name)
