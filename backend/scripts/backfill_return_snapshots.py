"""Backfill monthly return snapshots from the read-only cloud source.

The command is dry-run by default. Pass ``--apply`` to write all selected
months in one local database transaction after every cloud query succeeds.
"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.analytics import (
    AnalyticsDetailRow,
    AnalyticsImportBatch,
    MetricDefinition,
    MonthlyMetric,
)
from app.models.user import AuditLog, User
from app.services.analytics_sources import RETURN_COLUMNS, RETURN_SOURCE_NAME, fetch_return_items


def parse_month(value: str) -> date:
    try:
        return date.fromisoformat(f"{value}-01")
    except ValueError as exc:
        raise argparse.ArgumentTypeError("月份格式必须为 YYYY-MM") from exc


def month_range(start: date, end: date) -> list[date]:
    if start > end:
        raise ValueError("开始月份不能晚于结束月份")
    result: list[date] = []
    current = start
    while current <= end:
        result.append(current)
        current = date(current.year + (current.month == 12), current.month % 12 + 1, 1)
    return result


def source_summary(source: dict[str, object]) -> dict[str, object]:
    rows = list(source["rows"])
    return {
        "teams": int(source["row_count"]),
        "handled": sum(int(row["处理退货件数"]) for row in rows),
        "intercepted": sum(int(row["拦截件扣费件数"]) for row in rows),
        "unusual": sum(int(row["异常件扣费件数"]) for row in rows),
        "total": int(source["total"]),
    }


def backup_existing(months: list[date], metric: MetricDefinition) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = Path("storage/backups") / f"return_items_before_backfill_{timestamp}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with SessionLocal() as db:
        batches = db.scalars(
            select(AnalyticsImportBatch)
            .where(
                AnalyticsImportBatch.dataset_type == "return_items",
                AnalyticsImportBatch.month.in_(months),
            )
            .order_by(AnalyticsImportBatch.month, AnalyticsImportBatch.id)
        ).all()
        batch_rows = {
            batch.id: db.scalars(
                select(AnalyticsDetailRow)
                .where(AnalyticsDetailRow.batch_id == batch.id)
                .order_by(AnalyticsDetailRow.row_number)
            ).all()
            for batch in batches
        }
        metrics = db.scalars(
            select(MonthlyMetric).where(
                MonthlyMetric.metric_id == metric.id,
                MonthlyMetric.month.in_(months),
            )
        ).all()
        payload = {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "months": [month.strftime("%Y-%m") for month in months],
            "batches": [
                {
                    "id": batch.id,
                    "month": batch.month.isoformat(),
                    "original_name": batch.original_name,
                    "sheet_name": batch.sheet_name,
                    "mode": batch.mode,
                    "columns": batch.columns,
                    "row_count": batch.row_count,
                    "active": batch.active,
                    "created_by_id": batch.created_by_id,
                    "created_at": batch.created_at.isoformat() if batch.created_at else None,
                    "rows": [
                        {"row_number": row.row_number, "payload": row.payload}
                        for row in batch_rows[batch.id]
                    ],
                }
                for batch in batches
            ],
            "metrics": [
                {
                    "id": item.id,
                    "month": item.month.isoformat(),
                    "value": str(item.value),
                    "note": item.note,
                    "source_type": item.source_type,
                    "source_name": item.source_name,
                    "source_batch_id": item.source_batch_id,
                    "updated_by_id": item.updated_by_id,
                }
                for item in metrics
            ],
        }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path.resolve()


def main() -> None:
    parser = argparse.ArgumentParser(description="按月回填退货云端数据并形成系统快照")
    parser.add_argument("--start", required=True, type=parse_month, help="开始月份 YYYY-MM")
    parser.add_argument("--end", required=True, type=parse_month, help="结束月份 YYYY-MM")
    parser.add_argument("--apply", action="store_true", help="确认写入本地数据库")
    args = parser.parse_args()
    months = month_range(args.start, args.end)

    sources: dict[date, dict[str, object]] = {}
    for month in months:
        source = fetch_return_items(month)
        if list(source["columns"]) != RETURN_COLUMNS:
            raise RuntimeError(f"{month:%Y-%m} 云端字段与系统模板不一致")
        if int(source["row_count"]) <= 0 or int(source["total"]) <= 0:
            raise RuntimeError(f"{month:%Y-%m} 云端无有效退货数据，已停止整批回填")
        sources[month] = source

    preview = [
        {"month": month.strftime("%Y-%m"), **source_summary(sources[month])}
        for month in months
    ]
    if not args.apply:
        print(json.dumps({"mode": "dry-run", "months": preview}, ensure_ascii=False, indent=2))
        return

    with SessionLocal() as db:
        metric = db.scalar(
            select(MetricDefinition).where(MetricDefinition.code == "return_items")
        )
        if metric is None:
            raise RuntimeError("退货件数指标未配置")
        admin = db.scalar(
            select(User).where(User.username == "admin", User.is_active.is_(True))
        )
        admin_id = admin.id if admin else None

    backup_path = backup_existing(months, metric)
    results: list[dict[str, object]] = []
    with SessionLocal.begin() as db:
        metric = db.scalar(
            select(MetricDefinition).where(MetricDefinition.code == "return_items")
        )
        if metric is None:
            raise RuntimeError("退货件数指标未配置")
        for month in months:
            source = sources[month]
            existing = db.scalars(
                select(AnalyticsImportBatch).where(
                    AnalyticsImportBatch.dataset_type == "return_items",
                    AnalyticsImportBatch.month == month,
                    AnalyticsImportBatch.active.is_(True),
                )
            ).all()
            replaced_batch_ids = [batch.id for batch in existing]
            for batch in existing:
                batch.active = False

            batch = AnalyticsImportBatch(
                dataset_type="return_items",
                month=month,
                original_name=f"系统取数 · {RETURN_SOURCE_NAME}",
                sheet_name=f"{source['month_start']} 至 {source['month_end']}（不含）",
                mode="system",
                columns=list(source["columns"]),
                row_count=int(source["row_count"]),
                active=True,
                created_by_id=admin_id,
            )
            db.add(batch)
            db.flush()
            for row_number, row in enumerate(source["rows"], start=1):
                db.add(
                    AnalyticsDetailRow(
                        batch_id=batch.id,
                        row_number=row_number,
                        payload=dict(row),
                    )
                )

            target = db.scalar(
                select(MonthlyMetric).where(
                    MonthlyMetric.metric_id == metric.id,
                    MonthlyMetric.month == month,
                )
            )
            if target is None:
                target = MonthlyMetric(metric_id=metric.id, month=month, value=Decimal(0))
                db.add(target)
            target.value = Decimal(str(source["total"]))
            target.source_type = "system"
            target.source_name = RETURN_SOURCE_NAME
            target.source_batch_id = batch.id
            target.updated_by_id = admin_id
            target.note = "处理退货、拦截件扣费与异常件扣费三项按团队汇总"

            summary = source_summary(source)
            db.add(
                AuditLog(
                    user_id=admin_id,
                    action="analytics.return_snapshot_backfill",
                    resource=f"analytics:return_items:{month:%Y-%m}",
                    detail=json.dumps(
                        {
                            "source": RETURN_SOURCE_NAME,
                            "month_start": source["month_start"],
                            "month_end": source["month_end"],
                            "replaced_batch_ids": replaced_batch_ids,
                            **summary,
                        },
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                    ip_address="local-backfill",
                )
            )
            results.append(
                {
                    "month": month.strftime("%Y-%m"),
                    "batch_id": batch.id,
                    "replaced_batch_ids": replaced_batch_ids,
                    **summary,
                }
            )

    print(
        json.dumps(
            {"mode": "applied", "backup": str(backup_path), "months": results},
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
