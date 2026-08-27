"""Read-only statistics over migrated reconciliation workbooks."""

from __future__ import annotations

import json
import math
import re
from functools import lru_cache
from pathlib import Path

import pandas as pd

from app.core.config import settings

MONTH_PATTERN = re.compile(r"^\d{4}-\d{2}$")


def validate_month(month: str) -> str:
    if not MONTH_PATTERN.fullmatch(month):
        raise ValueError("月份格式必须为 YYYY-MM")
    return month


def output_folder(month: str) -> Path:
    return settings.storage_path / "output" / validate_month(month)


def result_file(month: str) -> Path:
    return output_folder(month) / "最终对账结果.xlsx"


def available_months() -> list[str]:
    root = settings.storage_path / "output"
    if not root.exists():
        return []
    return sorted(
        [
            item.name
            for item in root.iterdir()
            if item.is_dir() and MONTH_PATTERN.fullmatch(item.name)
        ],
        reverse=True,
    )


def read_result(month: str) -> pd.DataFrame:
    path = result_file(month)
    if not path.exists():
        return pd.DataFrame()
    return _read_cached(str(path), path.stat().st_mtime_ns).copy()


@lru_cache(maxsize=8)
def _read_cached(path: str, source_mtime_ns: int) -> pd.DataFrame:
    source = Path(path)
    cache_path = settings.storage_path / "cache" / f"express_rows_{source.parent.name}.pkl"
    if cache_path.exists() and cache_path.stat().st_mtime_ns >= source_mtime_ns:
        return pd.read_pickle(cache_path)
    frame = pd.read_excel(source, engine="openpyxl")
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_pickle(cache_path)
    return frame


def history_records() -> list[dict[str, object]]:
    records = []
    for month in available_months():
        folder = output_folder(month)
        log_path = folder / "run.log"
        content = (
            log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""
        )
        result = "无记录"
        if "成功 ✅" in content:
            result = "成功"
        elif "失败 ❌" in content:
            result = "失败"
        elapsed = ""
        for line in reversed(content.splitlines()):
            if line.startswith("耗时："):
                elapsed = line.replace("耗时：", "").strip()
                break
        files = [item for item in folder.rglob("*") if item.is_file()]
        records.append(
            {
                "month": month,
                "run_count": content.count("【第"),
                "last_result": result,
                "last_duration": elapsed,
                "file_count": len(files),
                "size_bytes": sum(item.stat().st_size for item in files),
                "downloadable": bool(files),
            }
        )
    return records


def _numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(0, index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce").fillna(0)


def month_stats(month: str) -> dict[str, object]:
    path = result_file(month)
    cached = _load_stats_cache(month, path)
    if cached is not None:
        return cached
    frame = read_result(month)
    base: dict[str, object] = {
        "month": month,
        "total_orders": 0,
        "matched_orders": 0,
        "unmatched_orders": 0,
        "total_amount": 0.0,
        "team_stats": [],
        "team_summary": [],
        "express_stats": [],
        "anomalies": [],
    }
    if frame.empty:
        return base

    base["total_orders"] = len(frame)
    matched = frame
    if "所属团队" in frame.columns:
        matched = frame[frame["所属团队"].fillna("").astype(str).str.strip() != "未匹配"].copy()
        base["unmatched_orders"] = int(len(frame) - len(matched))
    base["matched_orders"] = len(matched)
    matched["_amount"] = _numeric(matched, "单票应付金额")
    base["total_amount"] = round(float(matched["_amount"].sum()), 2)

    if "所属团队" in matched.columns:
        grouped = (
            matched.groupby("所属团队", dropna=False)
            .agg(amount=("_amount", "sum"), count=("_amount", "size"))
            .reset_index()
            .sort_values("amount", ascending=False)
        )
        base["team_stats"] = [
            {
                "team": str(row["所属团队"]),
                "amount": round(float(row["amount"]), 2),
                "count": int(row["count"]),
            }
            for _, row in grouped.iterrows()
        ]

    if "快递类型" in matched.columns:
        grouped = (
            matched.groupby("快递类型", dropna=False)
            .agg(amount=("_amount", "sum"), count=("_amount", "size"))
            .reset_index()
            .sort_values("amount", ascending=False)
        )
        total = float(grouped["amount"].sum())
        base["express_stats"] = [
            {
                "name": str(row["快递类型"]),
                "amount": round(float(row["amount"]), 2),
                "count": int(row["count"]),
                "pct": round(float(row["amount"]) / total * 100, 1) if total else 0,
            }
            for _, row in grouped.iterrows()
        ]

    anomaly_specs: list[tuple[str, str, pd.Series]] = []
    if "结算重量" in frame.columns:
        weight = _numeric(frame, "结算重量")
        anomaly_specs.append(("重量异常", "high", (weight <= 0) | (weight >= 50)))
    if "目的省份" in frame.columns:
        province = frame["目的省份"].fillna("").astype(str).str.strip()
        anomaly_specs.append(("省份为空", "mid", province == ""))
    if "所属团队" in frame.columns:
        anomaly_specs.append(("未匹配团队", "mid", frame["所属团队"] == "未匹配"))
    if "实际计算方式" in frame.columns and "单票应付金额" in frame.columns:
        anomaly_specs.append(
            (
                "单票金额为零",
                "mid",
                (frame["实际计算方式"] == "单票") & (_numeric(frame, "单票应付金额") == 0),
            )
        )
    anomalies = []
    for name, level, mask in anomaly_specs:
        count = int(mask.sum())
        if not count:
            continue
        samples = []
        if "运单号" in frame.columns:
            samples = frame.loc[mask, "运单号"].astype(str).head(5).tolist()
        anomalies.append(
            {
                "type": name,
                "level": level,
                "count": count,
                "pct": round(count / len(frame) * 100, 1),
                "samples": samples,
            }
        )
    base["anomalies"] = anomalies
    _save_stats_cache(month, path, base)
    return base


def _stats_cache_path(month: str) -> Path:
    return settings.storage_path / "cache" / f"express_stats_{month}.json"


def _load_stats_cache(month: str, source: Path) -> dict[str, object] | None:
    cache_path = _stats_cache_path(month)
    if not source.exists() or not cache_path.exists():
        return None
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
        if payload.get("source_mtime_ns") != source.stat().st_mtime_ns:
            return None
        return payload["data"]
    except (OSError, ValueError, KeyError):
        return None


def _save_stats_cache(month: str, source: Path, data: dict[str, object]) -> None:
    if not source.exists():
        return
    cache_path = _stats_cache_path(month)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps(
            {"source_mtime_ns": source.stat().st_mtime_ns, "data": data},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def trend_data() -> list[dict[str, object]]:
    points = []
    for month in reversed(available_months()):
        stats = month_stats(month)
        if stats["total_orders"]:
            points.append(
                {
                    "month": month,
                    "amount": stats["total_amount"],
                    "orders": stats["total_orders"],
                    "unmatched": stats["unmatched_orders"],
                }
            )
    return points


def unmatched_rows(month: str, limit: int = 200) -> list[dict[str, object]]:
    frame = read_result(month)
    if frame.empty or "所属团队" not in frame.columns:
        return []
    rows = frame[frame["所属团队"] == "未匹配"].head(limit)
    columns = [
        col for col in ("运单号", "目的省份", "结算重量", "快递类型", "实际计算方式") if col in rows
    ]
    return _records(rows[columns])


def preview_rows(month: str, page: int, size: int, keyword: str = "") -> dict[str, object]:
    frame = read_result(month)
    if frame.empty:
        return {"rows": [], "total": 0, "page": page, "size": size, "total_pages": 1}
    if keyword:
        mask = pd.Series(False, index=frame.index)
        for column in ("运单号", "所属团队", "目的省份", "快递类型"):
            if column in frame.columns:
                mask |= frame[column].fillna("").astype(str).str.contains(keyword, case=False)
        frame = frame[mask]
    total = len(frame)
    columns = [
        col
        for col in (
            "运单号",
            "所属团队",
            "目的省份",
            "结算重量",
            "快递类型",
            "实际计算方式",
            "单票应付金额",
        )
        if col in frame.columns
    ]
    page_frame = frame.iloc[(page - 1) * size : page * size]
    return {
        "rows": _records(page_frame[columns]),
        "total": total,
        "page": page,
        "size": size,
        "total_pages": max(1, math.ceil(total / size)),
    }


def anomaly_frame(month: str) -> pd.DataFrame:
    frame = read_result(month)
    if frame.empty:
        return frame
    mask = pd.Series(False, index=frame.index)
    if "结算重量" in frame.columns:
        weight = _numeric(frame, "结算重量")
        mask |= (weight <= 0) | (weight >= 50)
    if "目的省份" in frame.columns:
        mask |= frame["目的省份"].fillna("").astype(str).str.strip() == ""
    if "所属团队" in frame.columns:
        mask |= frame["所属团队"] == "未匹配"
    return frame[mask]


def _records(frame: pd.DataFrame) -> list[dict[str, object]]:
    clean = frame.astype(object).where(pd.notna(frame), None)
    return clean.to_dict(orient="records")
