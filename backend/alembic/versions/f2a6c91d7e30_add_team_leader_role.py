"""add team leader role

Revision ID: f2a6c91d7e30
Revises: d14a7c8e6f20
Create Date: 2026-08-28 14:35:00

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f2a6c91d7e30"
down_revision: str | Sequence[str] | None = "d14a7c8e6f20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    roles_table = sa.table(
        "roles",
        sa.column("code", sa.String),
        sa.column("name", sa.String),
        sa.column("description", sa.String),
        sa.column("is_system", sa.Boolean),
    )
    op.bulk_insert(
        roles_table,
        [
            {
                "code": "team_leader",
                "name": "组长",
                "description": "负责本组日常报销查看与审批。",
                "is_system": True,
            }
        ],
    )

    role_permissions_table = sa.table(
        "role_permissions",
        sa.column("role_code", sa.String),
        sa.column("permission_code", sa.String),
        sa.column("data_scope", sa.String),
    )
    op.bulk_insert(
        role_permissions_table,
        [
            {
                "role_code": "team_leader",
                "permission_code": "dashboard.view",
                "data_scope": "all",
            },
            {
                "role_code": "team_leader",
                "permission_code": "reimbursement.view",
                "data_scope": "team",
            },
            {
                "role_code": "team_leader",
                "permission_code": "reimbursement.create",
                "data_scope": "self",
            },
            {
                "role_code": "team_leader",
                "permission_code": "reimbursement.approve_supervisor",
                "data_scope": "team",
            },
        ],
    )


def downgrade() -> None:
    op.execute(sa.text("UPDATE users SET role = 'employee' WHERE role = 'team_leader'"))
    op.execute(sa.text("DELETE FROM user_roles WHERE role_code = 'team_leader'"))
    op.execute(sa.text("DELETE FROM role_permissions WHERE role_code = 'team_leader'"))
    op.execute(sa.text("DELETE FROM roles WHERE code = 'team_leader'"))
