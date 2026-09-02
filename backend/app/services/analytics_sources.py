"""Read-only source queries for operating analysis."""

from __future__ import annotations

from datetime import date, datetime, time

import pymysql
from pymysql.cursors import DictCursor

from app.core.config import settings

SHIPPING_SOURCE_NAME = "yibo.pre_matched_order（团队名称：yibo.team_info）"
SHIPPING_COLUMNS = ["团队名称", "发货单量", "数据发货占比", "备注"]
RETURN_SOURCE_NAME = (
    "yibo.after_sale_process、erp_entry_order、waybill_intercept、"
    "express_delivery_record（团队名称：yibo.team_info）"
)
RETURN_COLUMNS = [
    "团队名称",
    "处理退货件数",
    "拦截件扣费件数",
    "异常件扣费件数",
    "退货件数合计",
    "数据退货占比",
]
SHIPPING_QUERY = """
SELECT
    p.team_id AS teamId,
    ti.name AS teamName,
    COUNT(DISTINCT p.waybill_id) AS count
FROM pre_matched_order p
LEFT JOIN team_info ti ON ti.id = p.team_id
WHERE
    p.action_status IN (10, 20, 22, 28, 29, 30)
    AND p.part_logistics <> 2
    AND p.collect_time >= %s
    AND p.collect_time < %s
    AND p.warehouse_id IN (1, -1)
GROUP BY p.team_id, ti.name
ORDER BY p.team_id
""".strip()

RETURN_QUERY = """
WITH params AS (
    SELECT
        %s AS start_time,
        %s AS end_time,
        %s AS warehouse_id
),
quantity_data AS (
    SELECT
        a.team_id,
        SUM(IF(a.order_type IS NULL OR a.order_type <> 4, a.num, 0))
            AS return_goods_count,
        0 AS intercept_charge_count,
        0 AS unusual_charge_count
    FROM after_sale_process a
    CROSS JOIN params p
    WHERE a.deleted = 0
      AND a.warehouse_id = p.warehouse_id
      AND a.created_time >= p.start_time
      AND a.created_time < p.end_time
    GROUP BY a.team_id

    UNION ALL

    SELECT
        o.team_id,
        SUM(IF(i.inventory_type IS NULL OR i.inventory_type <> 'LP', i.plan_qty, 0))
            AS return_goods_count,
        0 AS intercept_charge_count,
        0 AS unusual_charge_count
    FROM erp_entry_order o
    INNER JOIN erp_entry_order_item i ON i.group_id = o.id
    CROSS JOIN params p
    WHERE o.deleted = 0
      AND i.deleted = 0
      AND o.order_type IN (12, 18)
      AND o.charge_amount > 0
      AND o.warehouse_id = p.warehouse_id
      AND o.created_time >= p.start_time
      AND o.created_time < p.end_time
    GROUP BY o.team_id

    UNION ALL

    SELECT
        w.team_id,
        0 AS return_goods_count,
        SUM(IF(w.charge_num IS NULL, w.total_num, w.charge_num))
            AS intercept_charge_count,
        0 AS unusual_charge_count
    FROM waybill_intercept w
    CROSS JOIN params p
    WHERE w.deleted = 0
      AND w.cost_bearer = 1
      AND (
          w.charge_num > 0
          OR (w.charge_num IS NULL AND w.total_num > 0)
      )
      AND w.warehouse_id = p.warehouse_id
      AND w.accept_time >= p.start_time
      AND w.accept_time < p.end_time
    GROUP BY w.team_id

    UNION ALL

    SELECT
        e.team_id,
        0 AS return_goods_count,
        0 AS intercept_charge_count,
        SUM(
            IF(
                e.warehouse_code IS NULL,
                IF(e.package_type = 3, e.num, 0),
                e.charge_num
            )
        ) AS unusual_charge_count
    FROM express_delivery_record e
    CROSS JOIN params p
    WHERE e.deleted = 0
      AND e.charge_type = 3
      AND e.warehouse_id = p.warehouse_id
      AND e.finish_time >= p.start_time
      AND e.finish_time < p.end_time
    GROUP BY e.team_id
)
SELECT
    q.team_id AS teamId,
    COALESCE(t.name, '') AS teamName,
    COALESCE(SUM(q.return_goods_count), 0) AS returnGoodsCount,
    COALESCE(SUM(q.intercept_charge_count), 0) AS interceptChargeCount,
    COALESCE(SUM(q.unusual_charge_count), 0) AS unusualChargeCount
FROM quantity_data q
LEFT JOIN team_info t ON t.id = q.team_id AND t.deleted = 0
GROUP BY q.team_id, t.name
ORDER BY q.team_id
""".strip()


def next_month(value: date) -> date:
    if value.month == 12:
        return date(value.year + 1, 1, 1)
    return date(value.year, value.month + 1, 1)


def fetch_shipping_orders(month_start: date) -> dict[str, object]:
    """Return per-team shipment counts without writing to the source database."""
    month_end = next_month(month_start)
    connection_config = {
        **settings.remote_database_config,
        "cursorclass": DictCursor,
        "connect_timeout": 10,
        "read_timeout": 60,
    }
    connection = None
    try:
        connection = pymysql.connect(**connection_config)
        with connection.cursor() as cursor:
            cursor.execute(SHIPPING_QUERY, (month_start, month_end))
            source_rows = cursor.fetchall()
    except pymysql.MySQLError as exc:
        raise RuntimeError("发货数据源连接或查询失败") from exc
    finally:
        if connection is not None:
            connection.close()

    total = sum(int(row["count"]) for row in source_rows)
    rows = []
    for row in source_rows:
        count = int(row["count"])
        rows.append(
            {
                "团队名称": str(row["teamName"] or row["teamId"] or "未分配团队"),
                "发货单量": count,
                "数据发货占比": round(count / total * 100, 2) if total else 0,
                "备注": "",
            }
        )
    return {
        "source_name": SHIPPING_SOURCE_NAME,
        "month_start": month_start.isoformat(),
        "month_end": month_end.isoformat(),
        "columns": SHIPPING_COLUMNS,
        "rows": rows,
        "row_count": len(rows),
        "total": total,
        "conditions": [
            "action_status IN (10, 20, 22, 28, 29, 30)",
            "part_logistics <> 2",
            "warehouse_id IN (1, -1)",
            "COUNT(DISTINCT waybill_id)",
            "团队名称取自 team_info.name",
        ],
    }


def fetch_return_items(month_start: date) -> dict[str, object]:
    """Return per-team return counts without writing to the source database."""
    month_end = next_month(month_start)
    start_time = datetime.combine(month_start, time(hour=8))
    end_time = datetime.combine(month_end, time(hour=8))
    connection_config = {
        **settings.remote_database_config,
        "cursorclass": DictCursor,
        "connect_timeout": 10,
        "read_timeout": 120,
    }
    connection = None
    try:
        connection = pymysql.connect(**connection_config)
        with connection.cursor() as cursor:
            cursor.execute(RETURN_QUERY, (start_time, end_time, 1))
            source_rows = cursor.fetchall()
    except pymysql.MySQLError as exc:
        raise RuntimeError("退货数据源连接或查询失败") from exc
    finally:
        if connection is not None:
            connection.close()

    prepared_rows: list[dict[str, object]] = []
    total = 0
    for row in source_rows:
        handled = int(row["returnGoodsCount"] or 0)
        intercepted = int(row["interceptChargeCount"] or 0)
        unusual = int(row["unusualChargeCount"] or 0)
        row_total = handled + intercepted + unusual
        total += row_total
        team_id = row.get("teamId")
        team_name = row.get("teamName") or (
            f"团队 {team_id}" if team_id is not None else "未分配团队"
        )
        prepared_rows.append(
            {
                "团队名称": str(team_name),
                "处理退货件数": handled,
                "拦截件扣费件数": intercepted,
                "异常件扣费件数": unusual,
                "退货件数合计": row_total,
                "数据退货占比": 0,
            }
        )

    for row in prepared_rows:
        row["数据退货占比"] = (
            round(int(row["退货件数合计"]) / total * 100, 2) if total else 0
        )

    return {
        "source_name": RETURN_SOURCE_NAME,
        "month_start": start_time.strftime("%Y-%m-%d %H:%M:%S"),
        "month_end": end_time.strftime("%Y-%m-%d %H:%M:%S"),
        "columns": RETURN_COLUMNS,
        "rows": prepared_rows,
        "row_count": len(prepared_rows),
        "total": total,
        "conditions": [
            "统计区间为所选月份1日08:00至次月1日08:00（不含结束时间）",
            "warehouse_id = 1",
            "旧系统处理退货排除 order_type = 4 赠品",
            "新系统仅统计 order_type IN (12, 18)、charge_amount > 0，排除 LP 赠品",
            "拦截件 charge_num 为空时使用 total_num，cost_bearer = 1",
            "异常件仅统计 charge_type = 3",
            "退货件数合计为处理退货、拦截扣费和异常扣费三项之和",
            "团队名称取自 team_info.name",
        ],
    }
