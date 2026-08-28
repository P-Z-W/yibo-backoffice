"""Background runner for the migrated reconciliation engine."""

from __future__ import annotations

import hashlib
import io
import queue
import sys
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.operations import JobRun, StoredFile

task_lock = threading.Lock()
log_queue: queue.Queue[str] = queue.Queue()
state: dict[str, object] = {
    "running": False,
    "success": False,
    "period": "",
    "elapsed": "",
    "message": "",
    "step": 0,
    "progress": 0,
}

STEP_PROGRESS = {0: 5, 1: 25, 2: 50, 3: 75, 4: 100}


def push_log(message: str) -> None:
    if message.startswith("__STEP__"):
        step = int(message.removeprefix("__STEP__"))
        state.update(step=step, progress=STEP_PROGRESS.get(step, 0))
    elif message.startswith("__STEP_FAIL__"):
        state["message"] = f"第 {message.removeprefix('__STEP_FAIL__')} 步运行失败"
    log_queue.put(message)


class LogCapture(io.TextIOBase):
    def __init__(self, original: io.TextIOBase, log_file: io.TextIOBase) -> None:
        self.original = original
        self.log_file = log_file

    def write(self, text: str) -> int:
        self.original.write(text)
        for line in text.splitlines():
            if line.strip():
                push_log(line.strip())
                self.log_file.write(line.strip() + "\n")
                self.log_file.flush()
        return len(text)

    def flush(self) -> None:
        self.original.flush()


def start_reconciliation(user_id: int) -> tuple[bool, str]:
    from app.domains.express import legacy_settings

    period = legacy_settings.PROCESS_MONTH
    data_folder = Path(legacy_settings.DATA_FOLDER)
    files = [path for path in data_folder.glob("*.xlsx") if not path.name.startswith("~")]
    if not files:
        return False, f"{period} 没有已上传的账单文件"

    with task_lock:
        if bool(state["running"]):
            return False, "当前已有快递对账任务运行中"
        state.update(
            running=True,
            success=False,
            period=period,
            elapsed="",
            message="任务启动",
            step=0,
            progress=0,
        )
        while not log_queue.empty():
            try:
                log_queue.get_nowait()
            except queue.Empty:
                break

    with SessionLocal() as db:
        job = JobRun(
            job_type="express_reconciliation", period=period, status="queued", created_by=user_id
        )
        db.add(job)
        db.commit()
        job_id = job.id

    thread = threading.Thread(target=_run_reconciliation, args=(job_id,), daemon=True)
    thread.start()
    return True, "任务已启动"


def _run_reconciliation(job_id: int) -> None:
    from app.domains.express import (
        legacy_settings,
        merge_express,
        order_db,
        order_matching,
        split_bill_by_team,
    )

    started = time.monotonic()
    started_at = datetime.now(UTC).replace(tzinfo=None)
    period = legacy_settings.PROCESS_MONTH
    output = Path(legacy_settings.OUTPUT_FOLDER)
    output.mkdir(parents=True, exist_ok=True)
    log_path = output / "run.log"
    original_stdout = sys.stdout
    success = False
    message = ""
    current_step = 1
    started_local = datetime.now()

    with SessionLocal() as db:
        job = db.get(JobRun, job_id)
        if job:
            job.status = "running"
            job.started_at = started_at
            db.commit()

    with log_path.open("a", encoding="utf-8") as log_file:
        try:
            existing = log_path.read_text(encoding="utf-8", errors="replace")
            run_count = existing.count("【第") + 1
            log_file.write("\n" + "=" * 60 + "\n")
            log_file.write(
                f"【第{run_count}次运行】{started_local.strftime('%Y-%m-%d %H:%M:%S')}\n"
            )
            log_file.write(f"处理月份：{period}\n" + "=" * 60 + "\n")
            log_file.flush()
            sys.stdout = LogCapture(original_stdout, log_file)
            push_log(f"🚀 开始处理 {period} 月份数据")
            push_log("__STEP__0")
            push_log(f"📌 第一步：从数据库下载 {period} 订单数据")
            order_frame = order_db.run_download_orders()
            if order_frame is None or order_frame.empty:
                raise RuntimeError("订单数据下载失败或为空")
            push_log("__STEP__1")
            current_step = 2
            push_log(f"📌 第二步：清洗合并 {period} 快递账单")
            express_frame = merge_express.run_merge_process()
            if express_frame is None or express_frame.empty:
                raise RuntimeError("快递账单合并失败或为空")
            push_log("__STEP__2")
            current_step = 3
            push_log(f"📌 第三步：运单号匹配对账（{period}）")
            order_matching.run_reconciliation()
            push_log("__STEP__3")
            current_step = 4
            push_log(f"📌 第四步：按团队拆分客户账单（{period}）")
            split_bill_by_team.main()
            push_log("__STEP__4")
            success = True
            message = "全部流程执行完成"
            push_log(f"🎉 {period} {message}")
        except Exception as exc:
            message = str(exc)
            push_log(f"__STEP_FAIL__{current_step}")
            push_log(f"❌ 程序运行异常：{message}")
        finally:
            sys.stdout = original_stdout
            elapsed_seconds = int(time.monotonic() - started)
            elapsed = f"{elapsed_seconds // 60}分{elapsed_seconds % 60}秒"
            result = "成功 ✅" if success else "失败 ❌"
            log_file.write("\n" + "-" * 60 + "\n")
            log_file.write(f"运行结果：{result}\n")
            log_file.write(f"结束时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            log_file.write(f"耗时：{elapsed}\n" + "-" * 60 + "\n")
            log_file.flush()

    try:
        elapsed_seconds = int(time.monotonic() - started)
        elapsed = f"{elapsed_seconds // 60}分{elapsed_seconds % 60}秒"
        _index_output_files(period)
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
            period=period,
            elapsed=elapsed,
            message=message,
            progress=100 if success else state["progress"],
        )
    finally:
        push_log("__DONE__")


def _index_output_files(period: str) -> None:
    root = settings.storage_path.resolve()
    folder = root / "output" / period
    if not folder.exists():
        return
    with SessionLocal() as db:
        for path in folder.rglob("*"):
            if not path.is_file():
                continue
            relative = path.resolve().relative_to(root).as_posix()
            target = db.scalar(select(StoredFile).where(StoredFile.relative_path == relative))
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if target is None:
                target = StoredFile(
                    category="business_output",
                    period=period,
                    original_name=path.name,
                    relative_path=relative,
                    size_bytes=path.stat().st_size,
                    sha256=digest,
                    source="new_system",
                )
                db.add(target)
            else:
                target.size_bytes = path.stat().st_size
                target.sha256 = digest
        db.commit()
