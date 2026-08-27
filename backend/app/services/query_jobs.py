"""Background SQL-query export service."""

from __future__ import annotations

import hashlib
import json
import queue
import re
import threading
import time
from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd
import pymysql
from sqlalchemy import select

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.operations import JobRun, QueryConfig, StoredFile

lock = threading.Lock()
log_queue: queue.Queue[str] = queue.Queue()
state: dict[str, object] = {
    "running": False,
    "success": False,
    "elapsed": "",
    "files": [],
    "message": "",
}
WRITE_PATTERN = re.compile(
    r"\b(insert|update|delete|drop|alter|truncate|create|replace|grant|revoke)\b",
    re.IGNORECASE,
)


def validate_read_query(sql: str) -> str:
    normalized = sql.strip().rstrip(";").strip()
    if not normalized.lower().startswith(("select", "with")):
        raise ValueError("仅允许 SELECT 或 WITH 查询")
    if WRITE_PATTERN.search(normalized):
        raise ValueError("查询中包含写入或结构变更语句")
    return normalized


def start_query_export(entry_ids: list[int], user_id: int) -> tuple[bool, str]:
    if not entry_ids:
        return False, "请至少选择一条查询"
    with lock:
        if bool(state["running"]):
            return False, "已有查询导出任务运行中"
        state.update(running=True, success=False, elapsed="", files=[], message="任务启动")
        while not log_queue.empty():
            try:
                log_queue.get_nowait()
            except queue.Empty:
                break

    with SessionLocal() as db:
        entries = db.scalars(select(QueryConfig).where(QueryConfig.id.in_(entry_ids))).all()
        try:
            tasks = [
                {
                    "id": row.id,
                    "filename": row.filename.strip() or row.query_name,
                    "sql": validate_read_query(row.sql_content),
                }
                for row in entries
            ]
        except ValueError as exc:
            state["running"] = False
            return False, str(exc)
        if not tasks:
            state["running"] = False
            return False, "没有找到有效查询"
        job = JobRun(
            job_type="query_export",
            period=date.today().isoformat(),
            status="queued",
            created_by=user_id,
        )
        db.add(job)
        db.commit()
        job_id = job.id

    threading.Thread(target=_run, args=(job_id, tasks), daemon=True).start()
    return True, "查询导出任务已启动"


def _run(job_id: int, tasks: list[dict[str, object]]) -> None:
    started = time.monotonic()
    today = date.today().isoformat()
    output_dir = settings.storage_path / "output" / "query_export" / today
    output_dir.mkdir(parents=True, exist_ok=True)
    generated: list[str] = []
    success = False
    message = ""
    with SessionLocal() as db:
        job = db.get(JobRun, job_id)
        if job:
            job.status = "running"
            job.started_at = datetime.now(UTC).replace(tzinfo=None)
            db.commit()
    connection = None
    try:
        connection = pymysql.connect(**settings.remote_database_config)
        log_queue.put(f"🚀 开始导出 {len(tasks)} 条查询")
        for task in tasks:
            raw_name = str(task["filename"]).strip() or "output"
            safe_name = re.sub(r'[\\/:*?"<>|]', "_", raw_name)
            filename = f"{today}_{safe_name}.xlsx"
            destination = output_dir / filename
            log_queue.put(f"📋 正在导出：{raw_name}")
            frame = pd.read_sql(str(task["sql"]), connection)
            frame.to_excel(destination, index=False)
            _remove_previous_versions(safe_name, destination)
            _index_file(destination)
            generated.append(filename)
            log_queue.put(f"✅ 已保存 {filename}，共 {len(frame)} 行")
        success = True
        message = f"全部导出完成，共 {len(generated)} 个文件"
        log_queue.put(f"🎉 {message}")
    except Exception as exc:
        message = str(exc)
        log_queue.put(f"❌ 导出异常：{message}")
    finally:
        if connection:
            connection.close()
        elapsed_seconds = int(time.monotonic() - started)
        elapsed = f"{elapsed_seconds // 60}分{elapsed_seconds % 60}秒"
        with SessionLocal() as db:
            job = db.get(JobRun, job_id)
            if job:
                job.status = "success" if success else "failed"
                job.finished_at = datetime.now(UTC).replace(tzinfo=None)
                job.elapsed_seconds = elapsed_seconds
                job.message = message
                db.commit()
        state.update(
            running=False,
            success=success,
            elapsed=elapsed,
            files=generated,
            message=message,
        )
        log_queue.put("__DONE__")


def _remove_previous_versions(safe_name: str, current: Path) -> None:
    root = settings.storage_path / "output" / "query_export"
    suffix = f"_{safe_name}.xlsx"
    for candidate in root.rglob(f"*{suffix}"):
        if candidate.resolve() != current.resolve():
            candidate.unlink(missing_ok=True)


def _index_file(path: Path) -> None:
    relative = path.relative_to(settings.storage_path).as_posix()
    with SessionLocal() as db:
        target = db.scalar(select(StoredFile).where(StoredFile.relative_path == relative))
        if target is None:
            target = StoredFile(
                category="query_export_output",
                period=date.today().isoformat(),
                original_name=path.name,
                relative_path=relative,
                size_bytes=path.stat().st_size,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                source="new_system",
            )
            db.add(target)
        db.commit()


def history() -> list[dict[str, object]]:
    root = settings.storage_path / "output" / "query_export"
    if not root.exists():
        return []
    records = []
    for folder in sorted([item for item in root.iterdir() if item.is_dir()], reverse=True):
        files = sorted([path.name for path in folder.glob("*.xlsx")])
        records.append({"date": folder.name, "file_count": len(files), "files": files})
    return records


def event_payload(message: str) -> str:
    return f"data: {json.dumps(message, ensure_ascii=False)}\n\n"
