"""add account access management

Revision ID: 7b31c9e228a4
Revises: 9f12a8d3b744
Create Date: 2026-08-27 20:10:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "7b31c9e228a4"
down_revision: str | Sequence[str] | None = "9f12a8d3b744"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


PERMISSIONS = (
    ("dashboard.view", "查看工作台", "工作台", "查看", 10, False),
    ("analytics.view", "查看经营分析", "经营分析", "查看", 20, False),
    ("analytics.manage", "维护经营分析", "经营分析", "维护", 21, False),
    ("express.view", "查看快递对账", "快递对账", "查看", 30, False),
    ("express.run", "运行快递对账", "快递对账", "运行", 31, False),
    ("express.download", "下载快递结果", "快递对账", "下载", 32, False),
    ("express.configure", "管理快递配置", "快递对账", "配置", 33, False),
    ("query.view", "查看数据查询", "数据查询", "查看", 40, False),
    ("query.run", "执行数据查询", "数据查询", "运行", 41, False),
    ("query.download", "下载查询结果", "数据查询", "下载", 42, False),
    ("query.configure", "管理查询配置", "数据查询", "配置", 43, False),
    ("salary.view", "查看员工工资", "员工工资", "查看", 50, False),
    ("salary.manage", "维护员工工资", "员工工资", "维护", 51, False),
    ("salary.export", "导出员工工资", "员工工资", "导出", 52, False),
    ("reimbursement.view", "查看报销单", "报销管理", "查看", 60, True),
    ("reimbursement.create", "填报报销单", "报销管理", "填报", 61, True),
    (
        "reimbursement.approve_supervisor",
        "主管审批报销",
        "报销管理",
        "主管审批",
        62,
        True,
    ),
    (
        "reimbursement.approve_finance",
        "财务审批报销",
        "报销管理",
        "财务审批",
        63,
        True,
    ),
    ("reimbursement.export", "导出报销审批表", "报销管理", "导出", 64, False),
    ("reimbursement.configure", "设置报销流程", "报销管理", "配置", 65, False),
    ("storage.view", "查看仓储费", "仓储费", "查看", 70, False),
    ("accounts.view", "查看账号", "账号与权限", "查看账号", 80, False),
    ("accounts.manage", "管理账号", "账号与权限", "管理账号", 81, False),
    ("roles.view", "查看角色权限", "账号与权限", "查看角色", 82, False),
    ("roles.manage", "管理角色权限", "账号与权限", "管理角色", 83, False),
    ("audit.view", "查看操作日志", "账号与权限", "查看日志", 84, False),
)


ROLE_GRANTS: dict[str, dict[str, str]] = {
    "admin": {code: "all" for code, *_ in PERMISSIONS},
    "management": {
        code: scope
        for code, scope in (
            ("dashboard.view", "all"),
            ("analytics.view", "all"),
            ("analytics.manage", "all"),
            ("express.view", "all"),
            ("express.download", "all"),
            ("query.view", "all"),
            ("query.run", "all"),
            ("query.download", "all"),
            ("salary.view", "all"),
            ("salary.export", "all"),
            ("reimbursement.view", "all"),
            ("reimbursement.create", "self"),
            ("reimbursement.export", "all"),
            ("storage.view", "all"),
        )
    },
    "supervisor": {
        code: scope
        for code, scope in (
            ("dashboard.view", "all"),
            ("analytics.view", "all"),
            ("express.view", "all"),
            ("express.run", "all"),
            ("express.download", "all"),
            ("query.view", "all"),
            ("query.run", "all"),
            ("query.download", "all"),
            ("reimbursement.view", "team"),
            ("reimbursement.create", "self"),
            ("reimbursement.approve_supervisor", "team"),
            ("reimbursement.export", "all"),
            ("storage.view", "all"),
        )
    },
    "finance": {
        code: scope
        for code, scope in (
            ("dashboard.view", "all"),
            ("analytics.view", "all"),
            ("express.view", "all"),
            ("express.download", "all"),
            ("query.view", "all"),
            ("query.run", "all"),
            ("query.download", "all"),
            ("salary.view", "all"),
            ("salary.manage", "all"),
            ("salary.export", "all"),
            ("reimbursement.view", "all"),
            ("reimbursement.create", "self"),
            ("reimbursement.approve_finance", "all"),
            ("reimbursement.export", "all"),
            ("storage.view", "all"),
        )
    },
    "operator": {
        code: scope
        for code, scope in (
            ("dashboard.view", "all"),
            ("analytics.view", "all"),
            ("express.view", "all"),
            ("express.run", "all"),
            ("express.download", "all"),
            ("express.configure", "all"),
            ("query.view", "all"),
            ("query.run", "all"),
            ("query.download", "all"),
            ("query.configure", "all"),
            ("reimbursement.view", "self"),
            ("reimbursement.create", "self"),
            ("storage.view", "all"),
        )
    },
    "employee": {
        "dashboard.view": "all",
        "reimbursement.view": "self",
        "reimbursement.create": "self",
    },
}


def upgrade() -> None:
    op.create_table(
        "roles",
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.Column("is_system", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("code"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "permissions",
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("module", sa.String(length=80), nullable=False),
        sa.Column("action", sa.String(length=40), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("supports_scope", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("code"),
    )
    op.create_index("ix_permissions_module", "permissions", ["module"])
    op.create_table(
        "role_permissions",
        sa.Column("role_code", sa.String(length=32), nullable=False),
        sa.Column("permission_code", sa.String(length=80), nullable=False),
        sa.Column("data_scope", sa.String(length=16), nullable=False),
        sa.ForeignKeyConstraint(["permission_code"], ["permissions.code"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["role_code"], ["roles.code"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("role_code", "permission_code"),
    )

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
                "code": "admin",
                "name": "系统管理员",
                "description": "拥有全系统权限，负责账号、角色和安全设置。",
                "is_system": True,
            },
            {
                "code": "management",
                "name": "经营管理",
                "description": "查看全局经营和业务数据，并维护经营复盘。",
                "is_system": True,
            },
            {
                "code": "supervisor",
                "name": "仓库主管",
                "description": "负责仓库业务和本组报销审批。",
                "is_system": True,
            },
            {
                "code": "finance",
                "name": "财务人员",
                "description": "管理员工工资、报销财务审批和财务导出。",
                "is_system": True,
            },
            {
                "code": "operator",
                "name": "运营对账",
                "description": "负责快递对账、查询导出及相关业务配置。",
                "is_system": True,
            },
            {
                "code": "employee",
                "name": "普通员工",
                "description": "使用基础工作台并填报、查看自己的报销。",
                "is_system": True,
            },
        ],
    )
    permissions_table = sa.table(
        "permissions",
        sa.column("code", sa.String),
        sa.column("name", sa.String),
        sa.column("module", sa.String),
        sa.column("action", sa.String),
        sa.column("sort_order", sa.Integer),
        sa.column("supports_scope", sa.Boolean),
    )
    op.bulk_insert(
        permissions_table,
        [
            {
                "code": code,
                "name": name,
                "module": module,
                "action": action,
                "sort_order": sort_order,
                "supports_scope": supports_scope,
            }
            for code, name, module, action, sort_order, supports_scope in PERMISSIONS
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
                "role_code": role_code,
                "permission_code": permission_code,
                "data_scope": data_scope,
            }
            for role_code, grants in ROLE_GRANTS.items()
            for permission_code, data_scope in grants.items()
        ],
    )

    op.add_column(
        "users",
        sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("users", sa.Column("password_changed_at", sa.DateTime(), nullable=True))
    op.create_foreign_key("fk_users_role_code", "users", "roles", ["role"], ["code"])


def downgrade() -> None:
    op.drop_constraint("fk_users_role_code", "users", type_="foreignkey")
    op.drop_column("users", "password_changed_at")
    op.drop_column("users", "must_change_password")
    op.drop_table("role_permissions")
    op.drop_index("ix_permissions_module", table_name="permissions")
    op.drop_table("permissions")
    op.drop_table("roles")
