"""Monthly customer and operating-record management APIs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ValidationError
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.db.session import get_db
from app.models.analytics import MetricDefinition, MonthlyMetric, MonthlyReview
from app.models.operation_record import (
    CustomerChangeRecord,
    CustomerServiceRecord,
    ShortVideoRecord,
    ValueAddedRecord,
)
from app.models.user import User
from app.schemas.operation_record import (
    CustomerChangeInput,
    CustomerServiceInput,
    ShortVideoInput,
    ValueAddedInput,
)
from app.services.audit import add_audit_log
from app.services.customer_sources import fetch_customer_source_preview
from app.services.operation_record_excel import (
    MAX_OPERATION_UPLOAD_BYTES,
    build_operation_export,
    build_operation_template,
    parse_operation_import,
)

router = APIRouter(prefix="/operation-records", tags=["客户与运营管理"])


@dataclass(frozen=True)
class RecordConfig:
    code: str
    name: str
    model: type
    schema: type[BaseModel]
    fields: tuple[str, ...]
    search_fields: tuple[str, ...]
    filter_field: str | None = None


CONFIGS = {
    "customer_changes": RecordConfig(
        "customer_changes",
        "客户管理",
        CustomerChangeRecord,
        CustomerChangeInput,
        ("change_type", "occurred_at", "customer_name", "source_channel", "quantity", "note"),
        ("customer_name", "source_channel", "note"),
        "change_type",
    ),
    "service_issues": RecordConfig(
        "service_issues",
        "客户服务管理",
        CustomerServiceRecord,
        CustomerServiceInput,
        (
            "team_name",
            "complaint_category",
            "issue_description",
            "verified_cause",
            "responsibility",
            "corrective_action",
            "status",
        ),
        (
            "team_name",
            "complaint_category",
            "issue_description",
            "verified_cause",
            "responsibility",
            "corrective_action",
        ),
        "status",
    ),
    "value_added": RecordConfig(
        "value_added",
        "增值服务",
        ValueAddedRecord,
        ValueAddedInput,
        (
            "team_id",
            "team_name",
            "service_code",
            "service_name",
            "service_group",
            "quantity",
        ),
        ("team_id", "team_name", "service_code", "service_name", "service_group"),
    ),
    "short_video": RecordConfig(
        "short_video",
        "短视频管理",
        ShortVideoRecord,
        ShortVideoInput,
        ("video_count", "video_type", "owner", "note"),
        ("video_type", "owner", "note"),
    ),
}


def month_date(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m").date().replace(day=1)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="月份格式不正确") from exc


def next_month(value: date) -> date:
    if value.month == 12:
        return date(value.year + 1, 1, 1)
    return date(value.year, value.month + 1, 1)


def customer_change_month_condition(selected: date):
    start = datetime.combine(selected, datetime.min.time())
    end = datetime.combine(next_month(selected), datetime.min.time())
    return or_(
        and_(
            CustomerChangeRecord.occurred_at.is_not(None),
            CustomerChangeRecord.occurred_at >= start,
            CustomerChangeRecord.occurred_at < end,
        ),
        and_(
            CustomerChangeRecord.occurred_at.is_(None),
            CustomerChangeRecord.month == selected,
        ),
    )


def record_month_condition(config: RecordConfig, selected: date):
    if config.code == "customer_changes":
        return customer_change_month_condition(selected)
    return config.model.month == selected


def occurrence_month(value: datetime | None, fallback: date | None) -> date:
    if value is not None:
        return date(value.year, value.month, 1)
    if fallback is not None:
        return fallback
    raise HTTPException(status_code=422, detail="客户变化记录缺少发生时间")


def ensure_month_editable(db: Session, selected: date) -> None:
    status = db.scalar(select(MonthlyReview.status).where(MonthlyReview.month == selected))
    if status == "archived":
        raise HTTPException(status_code=409, detail="该月份经营分析已归档，请先重新开启")


def get_config(dataset_type: str) -> RecordConfig:
    try:
        return CONFIGS[dataset_type]
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="业务台账类型不存在") from exc


def serialize_record(config: RecordConfig, row) -> dict[str, object]:
    payload = {
        "id": row.id,
        "month": row.month.strftime("%Y-%m") if row.month else "",
        **{
            field: value if (value := getattr(row, field)) is not None else ""
            for field in config.fields
        },
        "created_at": row.created_at.isoformat() if row.created_at else "",
        "updated_at": row.updated_at.isoformat() if row.updated_at else "",
    }
    if config.code == "customer_changes":
        payload["source_team_id"] = row.source_team_id
        payload["source_locked"] = row.source_team_id is not None
    return payload


def filters_for(
    config: RecordConfig,
    selected: date,
    keyword: str,
    filter_value: str,
) -> list[object]:
    model = config.model
    filters: list[object] = [record_month_condition(config, selected)]
    if keyword.strip():
        term = f"%{keyword.strip()}%"
        filters.append(or_(*(getattr(model, field).like(term) for field in config.search_fields)))
    if filter_value and config.filter_field:
        filters.append(getattr(model, config.filter_field) == filter_value)
    return filters


def summary_for(db: Session, config: RecordConfig, selected: date) -> dict[str, int]:
    model = config.model
    month_condition = record_month_condition(config, selected)
    total = db.scalar(select(func.count(model.id)).where(month_condition)) or 0
    if config.code == "customer_changes":
        values = {"total": total, "new": 0, "lost": 0, "prospective": 0}
        mapping = {"新进": "new", "流失": "lost", "意向": "prospective"}
        for change_type, quantity in db.execute(
            select(model.change_type, func.coalesce(func.sum(model.quantity), 0))
            .where(month_condition)
            .group_by(model.change_type)
        ):
            if change_type in mapping:
                values[mapping[change_type]] = int(quantity)
        return values
    if config.code == "service_issues":
        completed = db.scalar(
            select(func.count(model.id)).where(
                model.month == selected, model.status.in_(("已完成", "已关闭"))
            )
        ) or 0
        return {"total": total, "open": total - completed, "completed": completed}
    if config.code == "value_added":
        quantity = db.scalar(
            select(func.coalesce(func.sum(model.quantity), 0)).where(
                model.month == selected
            )
        ) or 0
        teams = db.scalar(
            select(func.count(func.distinct(model.team_name))).where(
                model.month == selected, model.team_name != ""
            )
        ) or 0
        services = db.scalar(
            select(func.count(func.distinct(model.service_name))).where(
                model.month == selected, model.service_name != ""
            )
        ) or 0
        return {
            "total": total,
            "quantity": int(quantity),
            "teams": teams,
            "services": services,
        }
    video_count = db.scalar(
        select(func.coalesce(func.sum(model.video_count), 0)).where(model.month == selected)
    ) or 0
    owners = db.scalar(
        select(func.count(func.distinct(model.owner))).where(
            model.month == selected, model.owner != ""
        )
    ) or 0
    return {"total": total, "video_count": int(video_count), "owners": owners}


def validate_payload(config: RecordConfig, payload: dict[str, object]) -> BaseModel:
    try:
        validated = config.schema.model_validate(payload)
    except ValidationError as exc:
        first = exc.errors()[0]
        raise HTTPException(status_code=422, detail=f"数据格式不正确：{first['msg']}") from exc
    data = validated.model_dump()
    for key, value in data.items():
        if isinstance(value, str):
            setattr(validated, key, value.strip())
    if config.code == "service_issues" and not validated.issue_description:
        raise HTTPException(status_code=422, detail="问题详细描述不能为空")
    if config.code == "value_added":
        if not validated.team_name:
            raise HTTPException(status_code=422, detail="团队名称不能为空")
        if not validated.service_name:
            raise HTTPException(status_code=422, detail="服务名称不能为空")
    return validated


def apply_payload(config: RecordConfig, target, validated: BaseModel) -> None:
    for field in config.fields:
        value = getattr(validated, field)
        if field in {"note", "verified_cause", "corrective_action"}:
            value = value or None
        setattr(target, field, value)


def sync_customer_metrics(db: Session, selected: date, user: User) -> None:
    metric_mapping = {
        "新进": "new_customers",
        "流失": "lost_customers",
        "意向": "prospective_customers",
    }
    quantities = {
        change_type: int(quantity)
        for change_type, quantity in db.execute(
            select(
                CustomerChangeRecord.change_type,
                func.coalesce(func.sum(CustomerChangeRecord.quantity), 0),
            )
            .where(customer_change_month_condition(selected))
            .group_by(CustomerChangeRecord.change_type)
        )
    }
    definitions = {
        row.code: row
        for row in db.scalars(
            select(MetricDefinition).where(MetricDefinition.code.in_(metric_mapping.values()))
        )
    }
    for change_type, code in metric_mapping.items():
        definition = definitions.get(code)
        if definition is None:
            continue
        target = db.scalar(
            select(MonthlyMetric).where(
                MonthlyMetric.metric_id == definition.id,
                MonthlyMetric.month == selected,
            )
        )
        if target is None:
            target = MonthlyMetric(metric_id=definition.id, month=selected, value=0)
            db.add(target)
        target.value = quantities.get(change_type, 0)
        target.note = "按客户管理模块当月记录汇总"
        target.source_type = "operation_module"
        target.source_name = "客户管理"
        target.source_batch_id = None
        target.updated_by_id = user.id


@router.get("/{dataset_type}")
def list_records(
    dataset_type: str,
    month: str = Query(pattern=r"^\d{4}-\d{2}$"),
    keyword: str = Query(default="", max_length=100),
    filter_value: str = Query(default="", max_length=30),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("operations_data.view")),
) -> dict[str, object]:
    config = get_config(dataset_type)
    selected = month_date(month)
    filters = filters_for(config, selected, keyword, filter_value)
    total = db.scalar(select(func.count(config.model.id)).where(*filters)) or 0
    rows = db.scalars(
        select(config.model)
        .where(*filters)
        .order_by(config.model.updated_at.desc(), config.model.id.desc())
        .offset((page - 1) * size)
        .limit(size)
    ).all()
    return {
        "records": [serialize_record(config, row) for row in rows],
        "total": total,
        "page": page,
        "size": size,
        "summary": summary_for(db, config, selected),
    }


@router.get("/customer_changes/source-preview")
def customer_source_preview(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("operations_data.view")),
) -> dict[str, object]:
    try:
        result = fetch_customer_source_preview()
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    registered_ids = set(
        db.scalars(
            select(CustomerChangeRecord.source_team_id).where(
                CustomerChangeRecord.source_team_id.is_not(None)
            )
        )
    )
    archived_months = set(
        db.scalars(select(MonthlyReview.month).where(MonthlyReview.status == "archived"))
    )
    rows = result["rows"]
    for row in rows:
        row["registered"] = row["team_id"] in registered_ids
        try:
            created_time = datetime.fromisoformat(str(row.get("created_time") or ""))
            row["archived"] = occurrence_month(created_time, None) in archived_months
        except ValueError:
            row["archived"] = False
    result["registered_total"] = sum(1 for row in rows if row["registered"])
    result["archived_total"] = sum(
        1 for row in rows if row["archived"] and not row["registered"]
    )
    result["pending_total"] = sum(
        1 for row in rows if not row["registered"] and not row["archived"]
    )
    return result


@router.post("/customer_changes/source-sync")
def sync_customer_source(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("operations_data.manage")),
) -> dict[str, object]:
    try:
        source = fetch_customer_source_preview()
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    existing_ids = set(
        db.scalars(
            select(CustomerChangeRecord.source_team_id).where(
                CustomerChangeRecord.source_team_id.is_not(None)
            )
        )
    )
    archived_months = set(
        db.scalars(select(MonthlyReview.month).where(MonthlyReview.status == "archived"))
    )
    affected_months: set[date] = set()
    created_count = 0
    skipped_existing = 0
    skipped_invalid = 0
    skipped_archived = 0

    for row in source["rows"]:
        team_id = row.get("team_id")
        created_time = row.get("created_time")
        if team_id is None or not created_time:
            skipped_invalid += 1
            continue
        if team_id in existing_ids:
            skipped_existing += 1
            continue
        try:
            occurred_at = datetime.fromisoformat(str(created_time))
        except ValueError:
            skipped_invalid += 1
            continue
        selected = occurrence_month(occurred_at, None)
        if selected in archived_months:
            skipped_archived += 1
            continue
        target = CustomerChangeRecord(
            month=None,
            occurred_at=occurred_at,
            source_team_id=int(team_id),
            change_type="新进",
            customer_name=str(row.get("team_name") or ""),
            source_channel="云端 team_source",
            quantity=1,
            note="按云端客户完整创建时间登记",
            created_by_id=user.id,
            updated_by_id=user.id,
        )
        db.add(target)
        existing_ids.add(int(team_id))
        affected_months.add(selected)
        created_count += 1

    if created_count:
        db.flush()
        for selected in sorted(affected_months):
            sync_customer_metrics(db, selected, user)
    add_audit_log(
        db,
        action="customer_source_sync",
        resource="customer_source:team_source",
        request=request,
        user=user,
        detail={
            "created": created_count,
            "existing": skipped_existing,
            "invalid": skipped_invalid,
            "archived": skipped_archived,
            "affected_months": [value.strftime("%Y-%m") for value in sorted(affected_months)],
        },
    )
    db.commit()
    return {
        "ok": True,
        "created_count": created_count,
        "skipped_existing": skipped_existing,
        "skipped_invalid": skipped_invalid,
        "skipped_archived": skipped_archived,
        "affected_months": [value.strftime("%Y-%m") for value in sorted(affected_months)],
    }


@router.get("/{dataset_type}/template")
def download_template(
    dataset_type: str,
    _: User = Depends(require_permission("operations_data.manage")),
) -> StreamingResponse:
    config = get_config(dataset_type)
    filename = quote(f"{config.name}导入模板.xlsx")
    return StreamingResponse(
        build_operation_template(dataset_type),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
    )


@router.get("/{dataset_type}/export")
def export_records(
    dataset_type: str,
    month: str = Query(pattern=r"^\d{4}-\d{2}$"),
    keyword: str = Query(default="", max_length=100),
    filter_value: str = Query(default="", max_length=30),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("operations_data.view")),
) -> StreamingResponse:
    config = get_config(dataset_type)
    selected = month_date(month)
    rows = db.scalars(
        select(config.model)
        .where(*filters_for(config, selected, keyword, filter_value))
        .order_by(config.model.updated_at.desc(), config.model.id.desc())
    ).all()
    if not rows:
        raise HTTPException(status_code=404, detail="当前筛选条件下没有可导出的数据")
    payloads = [
        {
            "record_id": row.id,
            **{
                field: value if (value := getattr(row, field)) is not None else ""
                for field in config.fields
            },
        }
        for row in rows
    ]
    filename = quote(f"{month}_{config.name}_{datetime.now():%Y%m%d_%H%M%S}.xlsx")
    return StreamingResponse(
        build_operation_export(dataset_type, payloads),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
    )


@router.post("/{dataset_type}/import")
def import_records(
    dataset_type: str,
    request: Request,
    month: str = Query(pattern=r"^\d{4}-\d{2}$"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("operations_data.manage")),
) -> dict[str, object]:
    config = get_config(dataset_type)
    selected = month_date(month)
    ensure_month_editable(db, selected)
    original_name = Path(file.filename or f"{config.name}.xlsx").name
    if Path(original_name).suffix.lower() != ".xlsx":
        raise HTTPException(status_code=422, detail="请上传 .xlsx 格式的业务台账")
    contents = file.file.read(MAX_OPERATION_UPLOAD_BYTES + 1)
    if len(contents) > MAX_OPERATION_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="导入文件不能超过 10MB")
    try:
        rows = parse_operation_import(dataset_type, contents)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    validated_rows: list[tuple[int | None, BaseModel]] = []
    for row in rows:
        excel_row = int(row.pop("_excel_row"))
        record_id = row.pop("record_id")
        try:
            validated = validate_payload(config, {**row, "month": month})
        except HTTPException as exc:
            raise HTTPException(
                status_code=422, detail=f"Excel 第 {excel_row} 行：{exc.detail}"
            ) from exc
        validated_rows.append((record_id, validated))

    created_count = 0
    updated_count = 0
    skipped_count = 0
    affected_customer_months: set[date] = set()
    for record_id, validated in validated_rows:
        target = db.get(config.model, record_id) if record_id else None
        target_month = (
            occurrence_month(target.occurred_at, target.month)
            if target is not None and dataset_type == "customer_changes"
            else target.month if target is not None else None
        )
        if record_id and (target is None or target_month != selected):
            raise HTTPException(
                status_code=422,
                detail=f"记录ID {record_id} 不属于 {month} 的{config.name}",
            )
        if target is not None and dataset_type == "customer_changes" and target.source_team_id:
            raise HTTPException(status_code=409, detail="云端登记的新进客户不允许通过 Excel 覆盖")
        if target is None:
            target = config.model(month=selected, created_by_id=user.id, updated_by_id=user.id)
            apply_payload(config, target, validated)
            db.add(target)
            if dataset_type == "customer_changes":
                effective = occurrence_month(target.occurred_at, target.month)
                ensure_month_editable(db, effective)
                affected_customer_months.add(effective)
            created_count += 1
            continue
        old_effective = target_month
        before = tuple(getattr(target, field) or "" for field in config.fields)
        apply_payload(config, target, validated)
        after = tuple(getattr(target, field) or "" for field in config.fields)
        if before == after:
            skipped_count += 1
        else:
            target.updated_by_id = user.id
            if dataset_type == "customer_changes":
                new_effective = occurrence_month(target.occurred_at, target.month)
                ensure_month_editable(db, new_effective)
                affected_customer_months.update((old_effective, new_effective))
            updated_count += 1
    if dataset_type == "customer_changes" and (created_count or updated_count):
        db.flush()
        for affected in sorted(affected_customer_months):
            sync_customer_metrics(db, affected, user)
    add_audit_log(
        db,
        action="operation_records_excel_import",
        resource=f"operation_records:{dataset_type}:{month}",
        request=request,
        user=user,
        detail={
            "filename": original_name,
            "created": created_count,
            "updated": updated_count,
            "skipped": skipped_count,
        },
    )
    db.commit()
    return {
        "ok": True,
        "created_count": created_count,
        "updated_count": updated_count,
        "skipped_count": skipped_count,
        "total_count": len(validated_rows),
    }


@router.post("/{dataset_type}", status_code=201)
def create_record(
    dataset_type: str,
    payload: dict[str, object],
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("operations_data.manage")),
) -> dict[str, object]:
    config = get_config(dataset_type)
    validated = validate_payload(config, payload)
    selected = month_date(validated.month)
    ensure_month_editable(db, selected)
    target = config.model(month=selected, created_by_id=user.id, updated_by_id=user.id)
    apply_payload(config, target, validated)
    effective = selected
    if dataset_type == "customer_changes":
        effective = occurrence_month(target.occurred_at, target.month)
        if effective != selected:
            ensure_month_editable(db, effective)
    target.updated_by_id = user.id
    db.add(target)
    db.flush()
    if dataset_type == "customer_changes":
        sync_customer_metrics(db, effective, user)
    add_audit_log(
        db,
        action="operation_record_create",
        resource=f"operation_record:{dataset_type}:{target.id}",
        request=request,
        user=user,
        detail={"month": validated.month},
    )
    db.commit()
    return serialize_record(config, target)


@router.put("/{dataset_type}/{record_id}")
def update_record(
    dataset_type: str,
    record_id: int,
    payload: dict[str, object],
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("operations_data.manage")),
) -> dict[str, object]:
    config = get_config(dataset_type)
    target = db.get(config.model, record_id)
    if target is None:
        raise HTTPException(status_code=404, detail="记录不存在")
    if dataset_type == "customer_changes" and target.source_team_id is not None:
        raise HTTPException(status_code=409, detail="云端登记的新进客户为历史记录，不允许修改")
    validated = validate_payload(config, payload)
    selected = month_date(validated.month)
    ensure_month_editable(db, selected)
    old_month = (
        occurrence_month(target.occurred_at, target.month)
        if dataset_type == "customer_changes"
        else target.month
    )
    if old_month != selected:
        ensure_month_editable(db, old_month)
    target.month = selected
    apply_payload(config, target, validated)
    new_month = (
        occurrence_month(target.occurred_at, target.month)
        if dataset_type == "customer_changes"
        else selected
    )
    if new_month != selected:
        ensure_month_editable(db, new_month)
    target.updated_by_id = user.id
    db.flush()
    if dataset_type == "customer_changes":
        if old_month != new_month:
            sync_customer_metrics(db, old_month, user)
        sync_customer_metrics(db, new_month, user)
    add_audit_log(
        db,
        action="operation_record_update",
        resource=f"operation_record:{dataset_type}:{record_id}",
        request=request,
        user=user,
        detail={"month": validated.month},
    )
    db.commit()
    return serialize_record(config, target)


@router.delete("/{dataset_type}/{record_id}")
def delete_record(
    dataset_type: str,
    record_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("operations_data.manage")),
) -> dict[str, object]:
    config = get_config(dataset_type)
    target = db.get(config.model, record_id)
    if target is None:
        raise HTTPException(status_code=404, detail="记录不存在")
    if dataset_type == "customer_changes" and target.source_team_id is not None:
        raise HTTPException(status_code=409, detail="云端登记的新进客户为历史记录，不允许删除")
    selected = (
        occurrence_month(target.occurred_at, target.month)
        if dataset_type == "customer_changes"
        else target.month
    )
    ensure_month_editable(db, selected)
    db.delete(target)
    db.flush()
    if dataset_type == "customer_changes":
        sync_customer_metrics(db, selected, user)
    add_audit_log(
        db,
        action="operation_record_delete",
        resource=f"operation_record:{dataset_type}:{record_id}",
        request=request,
        user=user,
        detail={"month": selected.strftime("%Y-%m")},
    )
    db.commit()
    return {"ok": True}
