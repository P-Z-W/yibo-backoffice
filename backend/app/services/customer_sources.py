"""Read-only cloud customer-source queries."""

from __future__ import annotations

from datetime import datetime

import pymysql
from pymysql.cursors import DictCursor

from app.core.config import settings

CUSTOMER_SOURCE_QUERY = """
SELECT
    team_id,
    team_name,
    created_time,
    cooperation_type,
    stock_send_price,
    viewable
FROM team_source
WHERE deleted = 0
  AND cooperation_type = %s
  AND (
      stock_send_price IS NULL
      OR stock_send_price < %s
  )
ORDER BY created_time DESC, id DESC
""".strip()

CUSTOMER_COOPERATION_TYPE = 20
CUSTOMER_STOCK_SEND_PRICE_MAX_EXCLUSIVE = 99900


def _bit_to_bool(value: object) -> bool | None:
    if value is None:
        return None
    if isinstance(value, (bytes, bytearray)):
        return int.from_bytes(value, byteorder="big") != 0
    return bool(value)


def fetch_customer_source_preview() -> dict[str, object]:
    """Return every active cloud-warehouse customer without modifying the cloud database."""
    connection_config = {
        **settings.remote_database_config,
        "cursorclass": DictCursor,
        "connect_timeout": 10,
        "read_timeout": 30,
    }
    connection = None
    try:
        connection = pymysql.connect(**connection_config)
        with connection.cursor() as cursor:
            cursor.execute(
                CUSTOMER_SOURCE_QUERY,
                (
                    CUSTOMER_COOPERATION_TYPE,
                    CUSTOMER_STOCK_SEND_PRICE_MAX_EXCLUSIVE,
                ),
            )
            source_rows = cursor.fetchall()
    except pymysql.MySQLError as exc:
        raise RuntimeError("客户源数据连接或查询失败") from exc
    finally:
        if connection is not None:
            connection.close()

    rows = [
        {
            "team_id": int(row["team_id"]) if row["team_id"] is not None else None,
            "team_name": str(row["team_name"] or ""),
            "created_time": (
                row["created_time"].isoformat(sep=" ", timespec="seconds")
                if isinstance(row["created_time"], datetime)
                else str(row["created_time"] or "")
            ),
            "cooperation_type": (
                int(row["cooperation_type"])
                if row["cooperation_type"] is not None
                else None
            ),
            "stock_send_price": (
                int(row["stock_send_price"])
                if row["stock_send_price"] is not None
                else None
            ),
            "viewable": _bit_to_bool(row["viewable"]),
        }
        for row in source_rows
    ]
    return {
        "source": "yibo.team_source",
        "filters": {
            "cooperation_type": CUSTOMER_COOPERATION_TYPE,
            "stock_send_price_lt": CUSTOMER_STOCK_SEND_PRICE_MAX_EXCLUSIVE,
            "stock_send_price_null_included": True,
        },
        "total": len(rows),
        "rows": rows,
    }
