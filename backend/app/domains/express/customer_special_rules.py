"""客户快递加收的可选特殊规则。"""

DEFAULT_XIXI_1KG_UNIT_PRICE = 10.0


def ensure_special_rule_table(cursor):
    """Confirm the Alembic-managed replacement table is available."""
    cursor.execute("SELECT 1 FROM team_special_rules LIMIT 1")
