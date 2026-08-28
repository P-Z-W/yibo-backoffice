"""Database-backed operating-analysis APIs."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_permission, user_has_role
from app.db.session import get_db
from app.models.analytics import (
    AnalyticsDetailRow,
    AnalyticsImportBatch,
    BusinessEvent,
    MetricDefinition,
    MonthlyMetric,
    MonthlyReview,
)
from app.models.user import User
from app.schemas.operations import MonthlyAnalyticsInput, MonthlyAnalyticsStatusInput
from app.services.analytics_import import (
    DATASET_DEFINITIONS,
    MAX_UPLOAD_BYTES,
    build_template,
    get_definition,
    parse_workbook,
    public_definitions,
    summarize_rows,
)
from app.services.audit import add_audit_log

router = APIRouter(prefix="/analytics", tags=["经营分析"])

SOURCE_LABELS = {
    "migration": "历史迁入",
    "manual": "系统手工录入",
    "excel": "Excel 上传",
    "system": "系统自动取数",
}


def month_date(month: str) -> date:
    try:
        return date.fromisoformat(f"{month}-01")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="月份格式必须为 YYYY-MM") from exc


def previous_month(value: date) -> date:
    if value.month == 1:
        return date(value.year - 1, 12, 1)
    return date(value.year, value.month - 1, 1)


def ensure_month_editable(db: Session, selected: date) -> None:
    review = db.scalar(select(MonthlyReview).where(MonthlyReview.month == selected))
    if review is not None and review.status == "archived":
        raise HTTPException(status_code=409, detail="该月份已归档，请先重新开启后再修改")


def detail_definition(dataset_type: str):
    try:
        return get_definition(dataset_type)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def read_excel_upload(file: UploadFile) -> tuple[str, bytes]:
    original_name = Path(file.filename or "经营分析分表.xlsx").name
    contents = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="导入文件不能超过 10MB")
    return original_name, contents


def parse_excel_upload(dataset_type: str, file: UploadFile) -> tuple[str, dict[str, object]]:
    definition = detail_definition(dataset_type)
    original_name, contents = read_excel_upload(file)
    try:
        parsed = parse_workbook(original_name, contents, definition)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return original_name, parsed


def active_detail_payloads(
    db: Session, dataset_type: str, selected: date
) -> list[dict[str, object]]:
    return [
        row.payload
        for row in db.scalars(
            select(AnalyticsDetailRow)
            .join(AnalyticsImportBatch)
            .where(
                AnalyticsImportBatch.dataset_type == dataset_type,
                AnalyticsImportBatch.month == selected,
                AnalyticsImportBatch.active.is_(True),
            )
            .order_by(AnalyticsImportBatch.created_at, AnalyticsDetailRow.row_number)
        )
    ]


@router.get("")
def analytics(
    month: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("analytics.view")),
) -> dict[str, object]:
    selected = month_date(month)
    previous = previous_month(selected)
    definitions = db.scalars(
        select(MetricDefinition)
        .where(MetricDefinition.enabled.is_(True))
        .order_by(MetricDefinition.sort_order)
    ).all()
    current_values = {
        row.metric_id: row
        for row in db.scalars(select(MonthlyMetric).where(MonthlyMetric.month == selected))
    }
    previous_values = {
        row.metric_id: row
        for row in db.scalars(select(MonthlyMetric).where(MonthlyMetric.month == previous))
    }
    active_batches = db.scalars(
        select(AnalyticsImportBatch)
        .where(
            AnalyticsImportBatch.month == selected,
            AnalyticsImportBatch.active.is_(True),
        )
        .order_by(AnalyticsImportBatch.created_at.desc(), AnalyticsImportBatch.id.desc())
    ).all()
    review = db.scalar(select(MonthlyReview).where(MonthlyReview.month == selected))
    user_ids = {
        value
        for value in [
            *(row.updated_by_id for row in current_values.values()),
            *(row.created_by_id for row in active_batches),
            review.updated_by_id if review else None,
        ]
        if value is not None
    }
    user_names = {
        user.id: user.display_name
        for user in db.scalars(select(User).where(User.id.in_(user_ids)))
    } if user_ids else {}
    items = []
    for definition in definitions:
        current = current_values.get(definition.id)
        prior = previous_values.get(definition.id)
        current_number = float(current.value) if current else None
        prior_number = float(prior.value) if prior else None
        change = (
            current_number - prior_number
            if current_number is not None and prior_number is not None
            else None
        )
        ratio = change / prior_number * 100 if change is not None and prior_number else None
        items.append(
            {
                "id": definition.id,
                "code": definition.code,
                "name": definition.name,
                "category": definition.category,
                "unit": definition.unit,
                "precision": definition.precision,
                "value": current_number,
                "previous_value": prior_number,
                "change": round(change, 4) if change is not None else None,
                "change_ratio": round(ratio, 2) if ratio is not None else None,
                "note": current.note if current else "",
                "source_type": current.source_type if current else None,
                "source_label": SOURCE_LABELS.get(current.source_type, current.source_type)
                if current
                else "暂无数据",
                "source_name": current.source_name if current else None,
                "updated_at": current.updated_at.isoformat() if current else None,
                "updated_by_name": user_names.get(current.updated_by_id) if current else None,
            }
        )
    definitions_by_code = {row.code: row for row in definitions}
    batches_by_dataset: dict[str, list[AnalyticsImportBatch]] = {}
    for batch in active_batches:
        batches_by_dataset.setdefault(batch.dataset_type, []).append(batch)
    completion_items = []
    for definition in DATASET_DEFINITIONS:
        batches = batches_by_dataset.get(definition.code, [])
        metric_rows = [
            current_values[metric_definition.id]
            for code in definition.metric_codes
            if (metric_definition := definitions_by_code.get(code)) is not None
            and metric_definition.id in current_values
        ]
        if batches:
            latest_batch = batches[0]
            state = "uploaded"
            label = "已上传"
            source_name = latest_batch.original_name
            updated_at = latest_batch.created_at
            updated_by_name = user_names.get(latest_batch.created_by_id)
            row_count = sum(batch.row_count for batch in batches)
        elif metric_rows:
            latest_metric = max(metric_rows, key=lambda row: row.updated_at)
            state = "summary_only"
            label = "总表已录入"
            source_name = latest_metric.source_name or SOURCE_LABELS.get(
                latest_metric.source_type, latest_metric.source_type
            )
            updated_at = latest_metric.updated_at
            updated_by_name = user_names.get(latest_metric.updated_by_id)
            row_count = 0
        else:
            state = "missing"
            label = "待补充"
            source_name = None
            updated_at = None
            updated_by_name = None
            row_count = 0
        completion_items.append(
            {
                "code": definition.code,
                "name": definition.name,
                "state": state,
                "label": label,
                "source_name": source_name,
                "row_count": row_count,
                "updated_at": updated_at.isoformat() if updated_at else None,
                "updated_by_name": updated_by_name,
            }
        )
    completed_count = sum(item["state"] != "missing" for item in completion_items)
    activity_candidates = [
        *(
            (row.updated_at, user_names.get(row.updated_by_id), SOURCE_LABELS.get(row.source_type))
            for row in current_values.values()
        ),
        *(
            (row.created_at, user_names.get(row.created_by_id), row.original_name)
            for row in active_batches
        ),
    ]
    if review:
        activity_candidates.append(
            (review.updated_at, user_names.get(review.updated_by_id), "月度复盘")
        )
    latest_activity = (
        max(activity_candidates, key=lambda item: item[0])
        if activity_candidates
        else None
    )
    events = db.scalars(
        select(BusinessEvent)
        .where(BusinessEvent.month == selected)
        .order_by(BusinessEvent.category, BusinessEvent.id)
    ).all()
    trend_rows = db.scalars(select(MonthlyMetric).order_by(MonthlyMetric.month)).all()
    trend: dict[str, list[dict[str, object]]] = {}
    definitions_by_id = {row.id: row for row in definitions}
    for row in trend_rows:
        definition = definitions_by_id.get(row.metric_id)
        if definition is None:
            continue
        trend.setdefault(definition.code, []).append(
            {"month": row.month.strftime("%Y-%m"), "value": float(row.value)}
        )
    return {
        "month": month,
        "previous_month": previous.strftime("%Y-%m"),
        "metrics": items,
        "review": {
            "summary": review.summary or "" if review else "",
            "highlights": review.highlights or "" if review else "",
            "issues": review.issues or "" if review else "",
            "risks": review.risks or "" if review else "",
            "next_plan": review.next_plan or "" if review else "",
            "status": review.status if review else "draft",
            "completed_at": review.completed_at.isoformat()
            if review and review.completed_at
            else None,
            "archived_at": review.archived_at.isoformat()
            if review and review.archived_at
            else None,
            "updated_at": review.updated_at.isoformat() if review else None,
            "updated_by_name": user_names.get(review.updated_by_id) if review else None,
        },
        "completion": {
            "completed": completed_count,
            "total": len(completion_items),
            "percent": round(completed_count / len(completion_items) * 100)
            if completion_items
            else 0,
            "items": completion_items,
        },
        "latest_activity": {
            "updated_at": latest_activity[0].isoformat(),
            "updated_by_name": latest_activity[1],
            "source": latest_activity[2],
        }
        if latest_activity
        else None,
        "events": [
            {
                "id": row.id,
                "category": row.category,
                "title": row.title,
                "description": row.description or "",
                "event_date": row.event_date.isoformat() if row.event_date else None,
            }
            for row in events
        ],
        "trend": trend,
    }


@router.put("")
def save_analytics(
    payload: MonthlyAnalyticsInput,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("analytics.manage")),
) -> dict[str, object]:
    selected = month_date(payload.month)
    ensure_month_editable(db, selected)
    valid_ids = set(db.scalars(select(MetricDefinition.id)).all())
    for item in payload.metrics:
        if item.metric_id not in valid_ids:
            raise HTTPException(status_code=400, detail=f"指标 {item.metric_id} 不存在")
        target = db.scalar(
            select(MonthlyMetric).where(
                MonthlyMetric.month == selected,
                MonthlyMetric.metric_id == item.metric_id,
            )
        )
        new_value = Decimal(item.value)
        if target is None:
            target = MonthlyMetric(
                metric_id=item.metric_id,
                month=selected,
                value=new_value,
                source_type="manual",
                source_name="系统手工录入",
                updated_by_id=user.id,
            )
            db.add(target)
        elif target.value != new_value:
            target.value = new_value
            target.source_type = "manual"
            target.source_name = "系统手工录入"
            target.source_batch_id = None
            target.updated_by_id = user.id
        target.note = item.note.strip() or None
    review = db.scalar(select(MonthlyReview).where(MonthlyReview.month == selected))
    if review is None:
        review = MonthlyReview(month=selected, status="draft")
        db.add(review)
    review.summary = payload.summary.strip() or None
    review.highlights = payload.highlights.strip() or None
    review.issues = payload.issues.strip() or None
    review.risks = payload.risks.strip() or None
    review.next_plan = payload.next_plan.strip() or None
    review.updated_by_id = user.id
    add_audit_log(
        db,
        action="analytics.save",
        resource=f"analytics:{payload.month}",
        request=request,
        user=user,
        detail={"metrics": len(payload.metrics), "review_status": review.status},
    )
    db.commit()
    return {"ok": True, "message": f"{payload.month} 经营数据已保存"}


@router.put("/status")
def update_analytics_status(
    payload: MonthlyAnalyticsStatusInput,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("analytics.manage")),
) -> dict[str, object]:
    selected = month_date(payload.month)
    review = db.scalar(select(MonthlyReview).where(MonthlyReview.month == selected))
    if review is None:
        review = MonthlyReview(month=selected, status="draft", updated_by_id=user.id)
        db.add(review)
    previous_status = review.status
    if previous_status == "archived" and payload.status != "archived":
        if not user_has_role(db, user, "admin"):
            raise HTTPException(status_code=403, detail="只有系统管理员可以重新开启已归档月份")
    now = datetime.now()
    review.status = payload.status
    review.updated_by_id = user.id
    if payload.status == "draft":
        review.completed_at = None
        review.archived_at = None
    elif payload.status == "completed":
        review.completed_at = now
        review.archived_at = None
    else:
        review.completed_at = review.completed_at or now
        review.archived_at = now
    add_audit_log(
        db,
        action="analytics.status",
        resource=f"analytics:{payload.month}",
        request=request,
        user=user,
        detail={"from": previous_status, "to": payload.status},
    )
    db.commit()
    return {"ok": True, "status": payload.status, "message": "月份状态已更新"}


@router.get("/detail-types")
def detail_types(
    _: User = Depends(require_permission("analytics.view")),
) -> list[dict[str, object]]:
    return public_definitions()


@router.get("/details/{dataset_type}/template")
def detail_template(
    dataset_type: str,
    _: User = Depends(require_permission("analytics.view")),
) -> StreamingResponse:
    definition = detail_definition(dataset_type)
    filename = quote(f"{definition.name}导入模板.xlsx")
    return StreamingResponse(
        build_template(definition),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
    )


@router.post("/details/{dataset_type}/preview")
def preview_detail_import(
    dataset_type: str,
    file: UploadFile = File(...),
    _: User = Depends(require_permission("analytics.manage")),
) -> dict[str, object]:
    original_name, parsed = parse_excel_upload(dataset_type, file)
    rows = parsed["rows"]
    summary = summarize_rows(dataset_type, rows)
    return {
        "original_name": original_name,
        "sheet_name": parsed["sheet_name"],
        "columns": parsed["columns"],
        "rows": parsed["preview_rows"],
        "row_count": parsed["row_count"],
        "warnings": parsed["warnings"],
        "summary": {code: float(value) for code, value in summary.items()},
    }


@router.post("/details/{dataset_type}/import")
def import_detail_rows(
    dataset_type: str,
    request: Request,
    month: str = Form(...),
    mode: str = Form(default="replace"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("analytics.manage")),
) -> dict[str, object]:
    definition = detail_definition(dataset_type)
    selected = month_date(month)
    ensure_month_editable(db, selected)
    if mode not in {"replace", "append"}:
        raise HTTPException(status_code=422, detail="导入方式必须为 replace 或 append")
    original_name, parsed = parse_excel_upload(dataset_type, file)

    if mode == "replace":
        existing_batches = db.scalars(
            select(AnalyticsImportBatch).where(
                AnalyticsImportBatch.dataset_type == dataset_type,
                AnalyticsImportBatch.month == selected,
                AnalyticsImportBatch.active.is_(True),
            )
        ).all()
        for existing in existing_batches:
            existing.active = False

    batch = AnalyticsImportBatch(
        dataset_type=dataset_type,
        month=selected,
        original_name=original_name,
        sheet_name=str(parsed["sheet_name"]),
        mode=mode,
        columns=list(parsed["columns"]),
        row_count=int(parsed["row_count"]),
        active=True,
        created_by_id=user.id,
    )
    db.add(batch)
    db.flush()
    for row_number, payload in enumerate(parsed["rows"], start=1):
        db.add(
            AnalyticsDetailRow(
                batch_id=batch.id,
                row_number=row_number,
                payload=payload,
            )
        )
    db.flush()

    summary = summarize_rows(dataset_type, active_detail_payloads(db, dataset_type, selected))
    definitions = {
        item.code: item
        for item in db.scalars(
            select(MetricDefinition).where(MetricDefinition.code.in_(summary))
        )
    }
    updated_metrics: list[dict[str, object]] = []
    for code, value in summary.items():
        metric = definitions.get(code)
        if metric is None:
            continue
        target = db.scalar(
            select(MonthlyMetric).where(
                MonthlyMetric.month == selected,
                MonthlyMetric.metric_id == metric.id,
            )
        )
        if target is None:
            target = MonthlyMetric(metric_id=metric.id, month=selected, value=value)
            db.add(target)
        else:
            target.value = value
        target.source_type = "excel"
        target.source_name = original_name
        target.source_batch_id = batch.id
        target.updated_by_id = user.id
        target.note = f"由{definition.name}分表自动汇总"
        updated_metrics.append({"code": code, "name": metric.name, "value": float(value)})

    add_audit_log(
        db,
        action="analytics.import",
        resource=f"analytics:{dataset_type}:{month}",
        request=request,
        user=user,
        detail={
            "dataset": definition.name,
            "filename": original_name,
            "sheet": parsed["sheet_name"],
            "mode": mode,
            "rows": parsed["row_count"],
        },
    )
    db.commit()
    return {
        "ok": True,
        "message": f"已导入 {parsed['row_count']} 行{definition.name}数据",
        "row_count": parsed["row_count"],
        "updated_metrics": updated_metrics,
        "warnings": parsed["warnings"],
    }


@router.get("/details/{dataset_type}")
def detail_rows(
    dataset_type: str,
    month: str,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("analytics.view")),
) -> dict[str, object]:
    definition = detail_definition(dataset_type)
    selected = month_date(month)
    filters = (
        AnalyticsImportBatch.dataset_type == dataset_type,
        AnalyticsImportBatch.month == selected,
        AnalyticsImportBatch.active.is_(True),
    )
    batches = db.scalars(
        select(AnalyticsImportBatch)
        .where(*filters)
        .order_by(AnalyticsImportBatch.created_at.desc())
    ).all()
    batch_user_ids = {batch.created_by_id for batch in batches if batch.created_by_id is not None}
    batch_user_names = {
        user.id: user.display_name
        for user in db.scalars(select(User).where(User.id.in_(batch_user_ids)))
    } if batch_user_ids else {}
    columns: list[str] = []
    for batch in reversed(batches):
        for column in batch.columns:
            if column not in columns:
                columns.append(column)

    total = db.scalar(
        select(func.count(AnalyticsDetailRow.id))
        .join(AnalyticsImportBatch)
        .where(*filters)
    ) or 0
    result = db.execute(
        select(AnalyticsDetailRow, AnalyticsImportBatch)
        .join(AnalyticsImportBatch)
        .where(*filters)
        .order_by(AnalyticsImportBatch.created_at.desc(), AnalyticsDetailRow.row_number)
        .offset((page - 1) * size)
        .limit(size)
    ).all()
    summary = summarize_rows(dataset_type, active_detail_payloads(db, dataset_type, selected))
    return {
        "dataset": {
            "code": definition.code,
            "name": definition.name,
            "description": definition.description,
            "summary_hint": definition.summary_hint,
        },
        "month": month,
        "columns": columns,
        "rows": [
            {
                "id": row.id,
                "row_number": row.row_number,
                "values": row.payload,
                "source_name": batch.original_name,
                "imported_at": batch.created_at.isoformat(),
            }
            for row, batch in result
        ],
        "total": total,
        "page": page,
        "size": size,
        "summary": {code: float(value) for code, value in summary.items()},
        "batches": [
            {
                "original_name": batch.original_name,
                "sheet_name": batch.sheet_name,
                "mode": batch.mode,
                "row_count": batch.row_count,
                "imported_at": batch.created_at.isoformat(),
                "imported_by_name": batch_user_names.get(batch.created_by_id),
            }
            for batch in batches
        ],
    }
