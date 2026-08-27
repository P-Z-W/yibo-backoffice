"""Idempotently migrate legacy database rows and local business files."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pymysql
import pymysql.cursors
from sqlalchemy import select

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.analytics import MetricDefinition
from app.models.operations import (
    ExpressCarrier,
    ExpressChargePrice,
    QueryConfig,
    SalaryRecord,
    StoredFile,
    SystemSetting,
    TeamExpressPrice,
    TeamSpecialRule,
)

ANALYTICS_METRICS = [
    ("shipping_orders", "发货单量", "发货", "单"),
    ("shipping_customer_change", "发货客户变化", "发货", "家"),
    ("shipping_value_added", "发货增值", "发货", "元"),
    ("return_items", "退货件数", "退货", "件"),
    ("return_customer_change", "退货客户变化", "退货", "家"),
    ("return_value_added", "退件增值", "退货", "元"),
    ("new_customers", "新进客户", "客户", "家"),
    ("lost_customers", "流失客户", "客户", "家"),
    ("prospective_customers", "意向客户", "客户", "家"),
    ("supplier_change", "供应商变化", "供应商", "家"),
    ("express_adjustment", "快递调整", "供应商", ""),
    ("staff_adjustment", "人员调整", "人员场地", "人"),
    ("site_adjustment", "场地调整", "人员场地", ""),
    ("planning_adjustment", "规划调整", "其他", ""),
    ("system_optimization", "系统优化", "其他", ""),
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def legacy_connection():
    config = dict(settings.local_database_config)
    config["database"] = settings.legacy_db_name
    config["cursorclass"] = pymysql.cursors.DictCursor
    return pymysql.connect(**config)


def copy_business_files() -> list[tuple[str, str, Path]]:
    legacy = settings.legacy_project_path.resolve()
    storage = settings.storage_path.resolve()
    if not legacy.is_dir():
        raise RuntimeError(f"旧系统目录不存在：{legacy}")
    storage.mkdir(parents=True, exist_ok=True)

    copied: list[tuple[str, str, Path]] = []
    roots = [("data", "express_input"), ("output", "business_output")]
    for folder, category in roots:
        source_root = legacy / folder
        destination_root = storage / folder
        for source in source_root.rglob("*"):
            if not source.is_file():
                continue
            relative = source.relative_to(source_root)
            destination = destination_root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            if not destination.exists() or destination.stat().st_size != source.stat().st_size:
                shutil.copy2(source, destination)
            actual_category = (
                "query_export_output"
                if folder == "output" and relative.parts[0] == "query_export"
                else category
            )
            copied.append((actual_category, relative.parts[0], destination))

    public_config = storage / "config"
    private_config = storage / "private"
    public_config.mkdir(parents=True, exist_ok=True)
    private_config.mkdir(parents=True, exist_ok=True)
    config_files = [
        (legacy / "config" / "price_config.xlsx", public_config / "price_config.xlsx", "config"),
        (
            legacy / "config" / "express_config.json",
            public_config / "express_config.json",
            "config",
        ),
        (
            legacy / "config" / "settings_override.json",
            public_config / "settings_override.json",
            "config",
        ),
        (
            legacy / "config" / "SQL-config.txt",
            private_config / "SQL-config.txt",
            "private_config",
        ),
    ]
    for source, destination, category in config_files:
        if not source.exists():
            continue
        shutil.copy2(source, destination)
        copied.append((category, "", destination))
    return copied


def upsert_database_rows(files: list[tuple[str, str, Path]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    with legacy_connection() as legacy, SessionLocal() as db:
        with legacy.cursor() as cursor:
            cursor.execute("SELECT * FROM yibo_express_charge_price ORDER BY id")
            charge_rows = cursor.fetchall()
            for row in charge_rows:
                target = db.scalar(
                    select(ExpressChargePrice).where(
                        ExpressChargePrice.express_type == row["express_type"]
                    )
                )
                if target is None:
                    target = ExpressChargePrice(express_type=row["express_type"])
                    db.add(target)
                target.charge_price = row["charge_price"]
            counts["express_charge_prices"] = len(charge_rows)

            cursor.execute("SELECT * FROM yibo_team_express_price ORDER BY seq, id")
            team_rows = cursor.fetchall()
            teams: dict[str, TeamExpressPrice] = {}
            for row in team_rows:
                target = db.scalar(
                    select(TeamExpressPrice).where(
                        TeamExpressPrice.team_name == row["team_name"].strip()
                    )
                )
                if target is None:
                    target = TeamExpressPrice(team_name=row["team_name"].strip())
                    db.add(target)
                for field in (
                    "seq",
                    "st_fee",
                    "st_avg",
                    "st_extra",
                    "zt_fee",
                    "zt_avg",
                    "zt_extra",
                ):
                    setattr(target, field, row[field] or 0)
                teams[target.team_name] = target
            db.flush()
            counts["team_express_prices"] = len(team_rows)

            cursor.execute("SELECT * FROM yibo_team_special_rule ORDER BY team_name")
            special_rows = cursor.fetchall()
            for row in special_rows:
                team_name = row["team_name"].strip()
                team = teams.get(team_name)
                if team is None:
                    team = TeamExpressPrice(team_name=team_name, seq=len(teams) + 1)
                    db.add(team)
                    db.flush()
                    teams[team_name] = team
                target = db.scalar(
                    select(TeamSpecialRule).where(TeamSpecialRule.team_id == team.id)
                )
                if target is None:
                    target = TeamSpecialRule(team_id=team.id)
                    db.add(target)
                target.xixi_1kg_unit_price = row["xixi_1kg_unit_price"] or 10
                target.special_note = row["special_note"]
            counts["team_special_rules"] = len(special_rows)

            cursor.execute("SELECT * FROM yibo_query_config ORDER BY id")
            query_rows = cursor.fetchall()
            for row in query_rows:
                target = db.get(QueryConfig, row["id"])
                if target is None:
                    target = QueryConfig(id=row["id"])
                    db.add(target)
                target.group_name = row["group_name"]
                target.query_name = row["query_name"]
                target.filename = row["filename"] or ""
                target.sql_content = row["sql_content"] or ""
            counts["query_configs"] = len(query_rows)

            cursor.execute("SELECT * FROM yibo_salary ORDER BY id")
            salary_rows = cursor.fetchall()
            for row in salary_rows:
                target = db.get(SalaryRecord, row["id"])
                if target is None:
                    target = SalaryRecord(id=row["id"])
                    db.add(target)
                for field in (
                    "name",
                    "team",
                    "year_month",
                    "base_salary",
                    "bonus",
                    "deduction",
                    "note",
                    "created_at",
                ):
                    setattr(target, field, row[field])
            counts["salary_records"] = len(salary_rows)

        carrier_path = settings.legacy_project_path / "config" / "express_config.json"
        carrier_data = {"express_list": []}
        if carrier_path.exists():
            carrier_data = json.loads(carrier_path.read_text(encoding="utf-8"))
        for index, row in enumerate(carrier_data.get("express_list", []), start=1):
            target = db.scalar(select(ExpressCarrier).where(ExpressCarrier.name == row["name"]))
            if target is None:
                target = ExpressCarrier(name=row["name"])
                db.add(target)
            target.identify_column = row["identify_column"]
            target.enabled = bool(row.get("enabled", True))
            target.sort_order = index
        counts["express_carriers"] = len(carrier_data.get("express_list", []))

        setting_values = {
            "express.extend_days_before": ("15", "订单查询向前扩展天数"),
            "express.extend_days_after": ("5", "订单查询向后扩展天数"),
        }
        override_path = settings.legacy_project_path / "config" / "settings_override.json"
        if override_path.exists():
            overrides = json.loads(override_path.read_text(encoding="utf-8"))
            setting_values["express.extend_days_before"] = (
                str(overrides.get("SQL_EXTEND_DAYS_BEFORE", 15)),
                "订单查询向前扩展天数",
            )
            setting_values["express.extend_days_after"] = (
                str(overrides.get("SQL_EXTEND_DAYS_AFTER", 5)),
                "订单查询向后扩展天数",
            )
        for key, (value, description) in setting_values.items():
            target = db.get(SystemSetting, key)
            if target is None:
                target = SystemSetting(key=key, value=value, description=description)
                db.add(target)
            else:
                target.value = value

        for index, (code, name, category, unit) in enumerate(ANALYTICS_METRICS, start=1):
            target = db.scalar(select(MetricDefinition).where(MetricDefinition.code == code))
            if target is None:
                db.add(
                    MetricDefinition(
                        code=code,
                        name=name,
                        category=category,
                        unit=unit,
                        sort_order=index,
                    )
                )
        counts["metric_definitions"] = len(ANALYTICS_METRICS)

        storage_root = settings.storage_path.resolve()
        for category, period_hint, path in files:
            relative_path = path.resolve().relative_to(storage_root).as_posix()
            target = db.scalar(select(StoredFile).where(StoredFile.relative_path == relative_path))
            if target is None:
                target = StoredFile(
                    category=category,
                    period=period_hint if len(period_hint) == 7 and period_hint[4] == "-" else "",
                    original_name=path.name,
                    relative_path=relative_path,
                    size_bytes=path.stat().st_size,
                    sha256=sha256(path),
                    source="legacy",
                )
                db.add(target)
            else:
                target.size_bytes = path.stat().st_size
                target.sha256 = sha256(path)
        counts["stored_files"] = len(files)
        db.commit()
    return counts


def main() -> None:
    files = copy_business_files()
    counts = upsert_database_rows(files)
    print("legacy_migration=complete")
    for name, count in sorted(counts.items()):
        print(f"{name}={count}")
    print(f"storage_bytes={sum(path.stat().st_size for _, _, path in files)}")


if __name__ == "__main__":
    main()
