"""Permission catalog and built-in role templates."""

from typing import TypedDict


class PermissionDefinition(TypedDict):
    code: str
    name: str
    module: str
    action: str
    sort_order: int
    supports_scope: bool


def permission(
    code: str,
    name: str,
    module: str,
    action: str,
    sort_order: int,
    *,
    supports_scope: bool = False,
) -> PermissionDefinition:
    return {
        "code": code,
        "name": name,
        "module": module,
        "action": action,
        "sort_order": sort_order,
        "supports_scope": supports_scope,
    }


PERMISSION_DEFINITIONS: tuple[PermissionDefinition, ...] = (
    permission("dashboard.view", "查看工作台", "工作台", "查看", 10),
    permission("analytics.view", "查看经营分析", "经营分析", "查看", 20),
    permission("analytics.manage", "维护经营分析", "经营分析", "维护", 21),
    permission("express.view", "查看快递对账", "快递对账", "查看", 30),
    permission("express.run", "运行快递对账", "快递对账", "运行", 31),
    permission("express.download", "下载快递结果", "快递对账", "下载", 32),
    permission("express.configure", "管理快递配置", "快递对账", "配置", 33),
    permission("query.view", "查看数据查询", "数据查询", "查看", 40),
    permission("query.run", "执行数据查询", "数据查询", "运行", 41),
    permission("query.download", "下载查询结果", "数据查询", "下载", 42),
    permission("query.configure", "管理查询配置", "数据查询", "配置", 43),
    permission("salary.view", "查看员工工资", "员工工资", "查看", 50),
    permission("salary.manage", "维护员工工资", "员工工资", "维护", 51),
    permission("salary.export", "导出员工工资", "员工工资", "导出", 52),
    permission(
        "reimbursement.view",
        "查看报销单",
        "报销管理",
        "查看",
        60,
        supports_scope=True,
    ),
    permission(
        "reimbursement.create",
        "填报报销单",
        "报销管理",
        "填报",
        61,
        supports_scope=True,
    ),
    permission(
        "reimbursement.approve_supervisor",
        "主管审批报销",
        "报销管理",
        "主管审批",
        62,
        supports_scope=True,
    ),
    permission(
        "reimbursement.approve_finance",
        "财务审批报销",
        "报销管理",
        "财务审批",
        63,
        supports_scope=True,
    ),
    permission("reimbursement.export", "导出报销数据", "报销管理", "导出", 64),
    permission("reimbursement.configure", "设置报销流程", "报销管理", "配置", 65),
    permission("storage.view", "查看仓储费", "仓储费", "查看", 70),
    permission("suppliers.view", "查看供应商", "供应商管理", "查看", 72),
    permission("suppliers.manage", "维护供应商", "供应商管理", "维护", 73),
    permission("operations_data.view", "查看业务台账", "客户与运营管理", "查看", 74),
    permission("operations_data.manage", "维护业务台账", "客户与运营管理", "维护", 75),
    permission("accounts.view", "查看账号", "账号与权限", "查看账号", 80),
    permission("accounts.manage", "管理账号", "账号与权限", "管理账号", 81),
    permission("roles.view", "查看角色权限", "账号与权限", "查看角色", 82),
    permission("roles.manage", "管理角色权限", "账号与权限", "管理角色", 83),
    permission("audit.view", "查看操作日志", "账号与权限", "查看日志", 84),
)


PERMISSION_CODES = frozenset(item["code"] for item in PERMISSION_DEFINITIONS)
SCOPES = frozenset({"self", "team", "all"})


BUILTIN_ROLES: tuple[dict[str, object], ...] = (
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
        "code": "team_leader",
        "name": "组长",
        "description": "负责本组日常报销查看与审批。",
        "is_system": True,
    },
    {
        "code": "finance",
        "name": "财务人员",
        "description": "管理员工工资，在系统内完成报销财务审批和数据导出。",
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
)


BUILTIN_ROLE_PERMISSIONS: dict[str, dict[str, str]] = {
    "admin": {code: "all" for code in PERMISSION_CODES},
    "management": {
        "dashboard.view": "all",
        "analytics.view": "all",
        "analytics.manage": "all",
        "express.view": "all",
        "express.download": "all",
        "query.view": "all",
        "query.run": "all",
        "query.download": "all",
        "salary.view": "all",
        "salary.export": "all",
        "reimbursement.view": "all",
        "reimbursement.create": "self",
        "reimbursement.export": "all",
        "storage.view": "all",
        "suppliers.view": "all",
        "suppliers.manage": "all",
        "operations_data.view": "all",
        "operations_data.manage": "all",
    },
    "supervisor": {
        "dashboard.view": "all",
        "analytics.view": "all",
        "express.view": "all",
        "express.run": "all",
        "express.download": "all",
        "query.view": "all",
        "query.run": "all",
        "query.download": "all",
        "reimbursement.view": "team",
        "reimbursement.create": "self",
        "reimbursement.approve_supervisor": "team",
        "reimbursement.export": "all",
        "storage.view": "all",
        "suppliers.view": "all",
        "operations_data.view": "all",
    },
    "team_leader": {
        "dashboard.view": "all",
        "reimbursement.view": "team",
        "reimbursement.create": "self",
        "reimbursement.approve_supervisor": "team",
    },
    "finance": {
        "dashboard.view": "all",
        "analytics.view": "all",
        "express.view": "all",
        "express.download": "all",
        "query.view": "all",
        "query.run": "all",
        "query.download": "all",
        "salary.view": "all",
        "salary.manage": "all",
        "salary.export": "all",
        "reimbursement.view": "all",
        "reimbursement.create": "self",
        "reimbursement.approve_finance": "all",
        "reimbursement.export": "all",
        "storage.view": "all",
        "suppliers.view": "all",
        "operations_data.view": "all",
    },
    "operator": {
        "dashboard.view": "all",
        "analytics.view": "all",
        "express.view": "all",
        "express.run": "all",
        "express.download": "all",
        "express.configure": "all",
        "query.view": "all",
        "query.run": "all",
        "query.download": "all",
        "query.configure": "all",
        "reimbursement.view": "self",
        "reimbursement.create": "self",
        "storage.view": "all",
        "suppliers.view": "all",
        "operations_data.view": "all",
    },
    "employee": {
        "dashboard.view": "all",
        "reimbursement.view": "self",
        "reimbursement.create": "self",
    },
}
