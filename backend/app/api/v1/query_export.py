"""Query configuration and export APIs."""

from __future__ import annotations

import queue
import time
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.session import get_db
from app.models.operations import QueryConfig
from app.models.user import User
from app.schemas.operations import QueryConfigInput
from app.services import query_jobs

router = APIRouter(prefix="/query-export", tags=["查询导出"])


def validate_sql(sql_content: str) -> None:
    try:
        query_jobs.validate_read_query(sql_content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def serialize(row: QueryConfig) -> dict[str, object]:
    preview = next(
        (
            line.strip()
            for line in row.sql_content.splitlines()
            if line.strip() and not line.strip().startswith("--")
        ),
        "",
    )
    return {
        "id": row.id,
        "group_name": row.group_name,
        "query_name": row.query_name,
        "filename": row.filename,
        "sql_content": row.sql_content,
        "sql_preview": preview[:100],
    }


@router.get("/configs")
def configs(
    db: Session = Depends(get_db), _: User = Depends(get_current_user)
) -> dict[str, object]:
    rows = db.scalars(
        select(QueryConfig).order_by(QueryConfig.group_name, QueryConfig.id.desc())
    ).all()
    groups: dict[str, list[dict[str, object]]] = {}
    for row in rows:
        groups.setdefault(row.group_name, []).append(serialize(row))
    return {"groups": groups, "history": query_jobs.history(), "job": dict(query_jobs.state)}


@router.post("/configs", status_code=status.HTTP_201_CREATED)
def add_config(
    payload: QueryConfigInput,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict[str, object]:
    if payload.sql_content.strip():
        validate_sql(payload.sql_content)
    target = QueryConfig(
        group_name=payload.group_name.strip(),
        query_name=f"new_{int(time.time() * 1000)}",
        filename=payload.filename.strip(),
        sql_content=payload.sql_content,
    )
    db.add(target)
    db.commit()
    db.refresh(target)
    return serialize(target)


@router.put("/configs/{config_id}")
def save_config(
    config_id: int,
    payload: QueryConfigInput,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict[str, object]:
    target = db.get(QueryConfig, config_id)
    if target is None:
        raise HTTPException(status_code=404, detail="查询配置不存在")
    validate_sql(payload.sql_content)
    target.group_name = payload.group_name.strip()
    target.filename = payload.filename.strip()
    target.sql_content = payload.sql_content
    db.commit()
    return serialize(target)


@router.delete("/configs/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_config(
    config_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> None:
    if db.get(QueryConfig, config_id) is None:
        raise HTTPException(status_code=404, detail="查询配置不存在")
    db.execute(delete(QueryConfig).where(QueryConfig.id == config_id))
    db.commit()


@router.post("/run")
def run_export(entry_ids: list[int], user: User = Depends(get_current_user)) -> dict[str, object]:
    ok, message = query_jobs.start_query_export(entry_ids, user.id)
    if not ok:
        raise HTTPException(status_code=409, detail=message)
    return {"ok": True, "message": message}


@router.get("/status")
def export_status(_: User = Depends(get_current_user)) -> dict[str, object]:
    return dict(query_jobs.state)


@router.get("/logs")
def logs(_: User = Depends(get_current_user)) -> StreamingResponse:
    def generate():
        while True:
            try:
                message = query_jobs.log_queue.get(timeout=20)
            except queue.Empty:
                message = "__PING__"
            yield query_jobs.event_payload(message)
            if message == "__DONE__":
                break

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.get("/history")
def history(_: User = Depends(get_current_user)) -> list[dict[str, object]]:
    return query_jobs.history()


@router.get("/download/{day}/{filename}")
def download(day: str, filename: str, _: User = Depends(get_current_user)) -> FileResponse:
    safe_day = Path(day).name
    safe_name = Path(filename).name
    if safe_day != day or safe_name != filename or not safe_name.endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="文件路径无效")
    path = settings.storage_path / "output" / "query_export" / safe_day / safe_name
    if not path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(path, filename=safe_name)
