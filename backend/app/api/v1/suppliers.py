"""Supplier master-data management APIs."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.db.session import get_db
from app.models.analytics import MetricDefinition, MonthlyMetric, MonthlyReview
from app.models.supplier import Supplier, SupplierChange
from app.models.user import User
from app.schemas.supplier import SupplierInput, SupplierStatusInput
from app.services.audit import add_audit_log
from app.services.supplier_excel import (
    MAX_SUPPLIER_UPLOAD_BYTES,
    build_supplier_export,
    build_supplier_template,
    parse_supplier_import,
)

router = APIRouter(prefix="/suppliers", tags=["供应商管理"])


def month_date(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m").date().replace(day=1)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="月份格式不正确") from exc


def normalize_name(value: str) -> str:
    return " ".join(value.split()).casefold()


def ensure_month_editable(db: Session, selected: date) -> None:
    status_value = db.scalar(
        select(MonthlyReview.status).where(MonthlyReview.month == selected)
    )
    if status_value == "archived":
        raise HTTPException(status_code=409, detail="该月份经营分析已归档，请先重新开启")


def supplier_snapshot(row: Supplier) -> dict[str, object]:
    return {
        "name": row.name,
        "contact_name": row.contact_name or "",
        "contact_phone": row.contact_phone or "",
        "address": row.address or "",
        "cooperation_start_date": (
            row.cooperation_start_date.isoformat() if row.cooperation_start_date else ""
        ),
        "product_types": row.product_types or "",
        "note": row.note or "",
        "is_active": row.is_active,
    }


def serialize_supplier(row: Supplier) -> dict[str, object]:
    return {
        "id": row.id,
        **supplier_snapshot(row),
        "created_at": row.created_at.isoformat() if row.created_at else "",
        "updated_at": row.updated_at.isoformat() if row.updated_at else "",
    }


def add_change(
    db: Session,
    supplier: Supplier,
    *,
    change_month: date,
    change_type: str,
    change_note: str,
    user: User,
) -> SupplierChange:
    change = SupplierChange(
        supplier_id=supplier.id,
        change_month=change_month,
        change_type=change_type,
        snapshot=supplier_snapshot(supplier),
        change_note=change_note.strip() or None,
        changed_by_id=user.id,
    )
    db.add(change)
    db.flush()
    return change


def sync_supplier_metric(db: Session, selected: date, user: User) -> None:
    metric = db.scalar(
        select(MetricDefinition).where(MetricDefinition.code == "supplier_change")
    )
    if metric is None:
        return
    value = db.scalar(
        select(func.count(func.distinct(SupplierChange.supplier_id))).where(
            SupplierChange.change_month == selected
        )
    ) or 0
    target = db.scalar(
        select(MonthlyMetric).where(
            MonthlyMetric.metric_id == metric.id,
            MonthlyMetric.month == selected,
        )
    )
    if target is None:
        target = MonthlyMetric(metric_id=metric.id, month=selected, value=value)
        db.add(target)
    else:
        target.value = value
    target.note = "按供应商管理模块当月变更供应商去重汇总"
    target.source_type = "supplier_module"
    target.source_name = "供应商管理"
    target.source_batch_id = None
    target.updated_by_id = user.id


def duplicate_supplier_id(
    db: Session, normalized: str, exclude_id: int | None = None
) -> int | None:
    statement = select(Supplier.id).where(Supplier.normalized_name == normalized)
    if exclude_id is not None:
        statement = statement.where(Supplier.id != exclude_id)
    return db.scalar(statement)


def supplier_filters(keyword: str, active: bool | None) -> list[object]:
    filters: list[object] = []
    if keyword.strip():
        term = f"%{keyword.strip()}%"
        filters.append(
            or_(
                Supplier.name.like(term),
                Supplier.contact_name.like(term),
                Supplier.contact_phone.like(term),
                Supplier.product_types.like(term),
            )
        )
    if active is not None:
        filters.append(Supplier.is_active.is_(active))
    return filters


@router.get("")
def list_suppliers(
    keyword: str = Query(default="", max_length=100),
    active: bool | None = None,
    month: str = Query(default="", pattern=r"^(|\d{4}-\d{2})$"),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("suppliers.view")),
) -> dict[str, object]:
    selected = month_date(month) if month else date.today().replace(day=1)
    filters = supplier_filters(keyword, active)
    total = db.scalar(select(func.count(Supplier.id)).where(*filters)) or 0
    records = db.scalars(
        select(Supplier)
        .where(*filters)
        .order_by(Supplier.is_active.desc(), Supplier.name)
        .offset((page - 1) * size)
        .limit(size)
    ).all()
    all_total = db.scalar(select(func.count(Supplier.id))) or 0
    active_total = db.scalar(
        select(func.count(Supplier.id)).where(Supplier.is_active.is_(True))
    ) or 0
    changed = db.scalar(
        select(func.count(func.distinct(SupplierChange.supplier_id))).where(
            SupplierChange.change_month == selected
        )
    ) or 0
    added = db.scalar(
        select(func.count(func.distinct(SupplierChange.supplier_id))).where(
            SupplierChange.change_month == selected,
            SupplierChange.change_type == "created",
        )
    ) or 0
    return {
        "records": [serialize_supplier(row) for row in records],
        "total": total,
        "page": page,
        "size": size,
        "summary": {
            "total": all_total,
            "active": active_total,
            "inactive": all_total - active_total,
            "month_added": added,
            "month_changed": changed,
        },
    }


@router.get("/changes")
def list_supplier_changes(
    month: str = Query(pattern=r"^\d{4}-\d{2}$"),
    limit: int = Query(default=100, ge=1, le=300),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("suppliers.view")),
) -> list[dict[str, object]]:
    selected = month_date(month)
    rows = db.execute(
        select(SupplierChange, Supplier, User)
        .join(Supplier, Supplier.id == SupplierChange.supplier_id)
        .outerjoin(User, User.id == SupplierChange.changed_by_id)
        .where(SupplierChange.change_month == selected)
        .order_by(SupplierChange.created_at.desc(), SupplierChange.id.desc())
        .limit(limit)
    ).all()
    return [
        {
            "id": change.id,
            "supplier_id": supplier.id,
            "supplier_name": str(change.snapshot.get("name") or supplier.name),
            "change_month": change.change_month.strftime("%Y-%m"),
            "change_type": change.change_type,
            "change_note": change.change_note or "",
            "operator_name": operator.display_name if operator else "系统/历史维护",
            "snapshot": change.snapshot,
            "created_at": change.created_at.isoformat() if change.created_at else "",
        }
        for change, supplier, operator in rows
    ]


@router.get("/template")
def download_supplier_template(
    _: User = Depends(require_permission("suppliers.manage")),
) -> StreamingResponse:
    filename = quote("供应商导入模板.xlsx")
    return StreamingResponse(
        build_supplier_template(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{filename}",
            "Cache-Control": "no-store",
        },
    )


@router.get("/export")
def export_suppliers(
    keyword: str = Query(default="", max_length=100),
    active: bool | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("suppliers.view")),
) -> StreamingResponse:
    filters = supplier_filters(keyword, active)
    rows = db.scalars(
        select(Supplier)
        .where(*filters)
        .order_by(Supplier.is_active.desc(), Supplier.name)
    ).all()
    if not rows:
        raise HTTPException(status_code=404, detail="当前筛选条件下没有可导出的供应商")
    filename = quote(f"供应商档案_{datetime.now():%Y%m%d_%H%M%S}.xlsx")
    return StreamingResponse(
        build_supplier_export(list(rows)),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
    )


@router.post("/import")
def import_suppliers(
    request: Request,
    month: str = Query(pattern=r"^\d{4}-\d{2}$"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("suppliers.manage")),
) -> dict[str, object]:
    selected = month_date(month)
    ensure_month_editable(db, selected)
    original_name = Path(file.filename or "供应商导入.xlsx").name
    if Path(original_name).suffix.lower() != ".xlsx":
        raise HTTPException(status_code=422, detail="请上传 .xlsx 格式的供应商表")
    contents = file.file.read(MAX_SUPPLIER_UPLOAD_BYTES + 1)
    if len(contents) > MAX_SUPPLIER_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="导入文件不能超过 10MB")
    try:
        imported_rows = parse_supplier_import(contents)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    existing = {
        row.normalized_name: row for row in db.scalars(select(Supplier)).all()
    }
    created_count = 0
    updated_count = 0
    skipped_count = 0
    for row in imported_rows:
        normalized = normalize_name(row["name"])
        target = existing.get(normalized)
        if target is None:
            target = Supplier(
                name=row["name"],
                normalized_name=normalized,
                contact_name=row["contact_name"],
                contact_phone=row["contact_phone"],
                address=row["address"],
                cooperation_start_date=row["cooperation_start_date"],
                product_types=row["product_types"],
                note=row["note"] or None,
                is_active=row["is_active"] if row["is_active"] is not None else True,
                created_by_id=user.id,
                updated_by_id=user.id,
            )
            db.add(target)
            db.flush()
            existing[normalized] = target
            add_change(
                db,
                target,
                change_month=selected,
                change_type="created",
                change_note=row["change_note"] or f"Excel 导入：{original_name}",
                user=user,
            )
            created_count += 1
            continue

        before = supplier_snapshot(target)
        target.name = row["name"]
        target.contact_name = row["contact_name"]
        target.contact_phone = row["contact_phone"]
        target.address = row["address"]
        target.cooperation_start_date = row["cooperation_start_date"]
        target.product_types = row["product_types"]
        if row["note"] is not None:
            target.note = row["note"] or None
        if row["is_active"] is not None:
            target.is_active = row["is_active"]
        after = supplier_snapshot(target)
        if before == after and not row["change_note"]:
            skipped_count += 1
            continue
        target.updated_by_id = user.id
        non_status_changed = any(
            before[key] != after[key] for key in before if key != "is_active"
        )
        if before["is_active"] != after["is_active"] and not non_status_changed:
            change_type = "activated" if target.is_active else "deactivated"
        else:
            change_type = "updated"
        add_change(
            db,
            target,
            change_month=selected,
            change_type=change_type,
            change_note=row["change_note"] or f"Excel 导入：{original_name}",
            user=user,
        )
        updated_count += 1

    changed_count = created_count + updated_count
    if changed_count:
        sync_supplier_metric(db, selected, user)
    add_audit_log(
        db,
        action="supplier_excel_import",
        resource=f"suppliers:{month}",
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
        "message": f"导入完成：新增 {created_count} 家，更新 {updated_count} 家",
        "created_count": created_count,
        "updated_count": updated_count,
        "skipped_count": skipped_count,
        "total_count": len(imported_rows),
    }


@router.post("", status_code=status.HTTP_201_CREATED)
def create_supplier(
    payload: SupplierInput,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("suppliers.manage")),
) -> dict[str, object]:
    selected = month_date(payload.change_month)
    ensure_month_editable(db, selected)
    name = " ".join(payload.name.split())
    if not name:
        raise HTTPException(status_code=422, detail="供应商名称不能为空")
    normalized = normalize_name(name)
    if duplicate_supplier_id(db, normalized) is not None:
        raise HTTPException(status_code=409, detail="供应商名称已存在")
    target = Supplier(
        name=name,
        normalized_name=normalized,
        contact_name=payload.contact_name.strip(),
        contact_phone=payload.contact_phone.strip(),
        address=payload.address.strip(),
        cooperation_start_date=payload.cooperation_start_date,
        product_types=payload.product_types.strip(),
        note=payload.note.strip() or None,
        is_active=True,
        created_by_id=user.id,
        updated_by_id=user.id,
    )
    db.add(target)
    db.flush()
    add_change(
        db,
        target,
        change_month=selected,
        change_type="created",
        change_note=payload.change_note,
        user=user,
    )
    sync_supplier_metric(db, selected, user)
    add_audit_log(
        db,
        action="supplier_create",
        resource=f"supplier:{target.id}",
        request=request,
        user=user,
        detail={"name": target.name, "change_month": payload.change_month},
    )
    db.commit()
    db.refresh(target)
    return serialize_supplier(target)


@router.put("/{supplier_id}")
def update_supplier(
    supplier_id: int,
    payload: SupplierInput,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("suppliers.manage")),
) -> dict[str, object]:
    target = db.get(Supplier, supplier_id)
    if target is None:
        raise HTTPException(status_code=404, detail="供应商不存在")
    selected = month_date(payload.change_month)
    ensure_month_editable(db, selected)
    name = " ".join(payload.name.split())
    if not name:
        raise HTTPException(status_code=422, detail="供应商名称不能为空")
    normalized = normalize_name(name)
    if duplicate_supplier_id(db, normalized, target.id) is not None:
        raise HTTPException(status_code=409, detail="供应商名称已存在")
    before = supplier_snapshot(target)
    target.name = name
    target.normalized_name = normalized
    target.contact_name = payload.contact_name.strip()
    target.contact_phone = payload.contact_phone.strip()
    target.address = payload.address.strip()
    target.cooperation_start_date = payload.cooperation_start_date
    target.product_types = payload.product_types.strip()
    target.note = payload.note.strip() or None
    target.updated_by_id = user.id
    after = supplier_snapshot(target)
    if before == after and not payload.change_note.strip():
        raise HTTPException(status_code=422, detail="供应商信息没有发生变化")
    add_change(
        db,
        target,
        change_month=selected,
        change_type="updated",
        change_note=payload.change_note,
        user=user,
    )
    sync_supplier_metric(db, selected, user)
    add_audit_log(
        db,
        action="supplier_update",
        resource=f"supplier:{target.id}",
        request=request,
        user=user,
        detail={
            "name": target.name,
            "change_month": payload.change_month,
            "before": before,
            "after": after,
        },
    )
    db.commit()
    return serialize_supplier(target)


@router.patch("/{supplier_id}/status")
def update_supplier_status(
    supplier_id: int,
    payload: SupplierStatusInput,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("suppliers.manage")),
) -> dict[str, object]:
    target = db.get(Supplier, supplier_id)
    if target is None:
        raise HTTPException(status_code=404, detail="供应商不存在")
    if target.is_active == payload.is_active:
        raise HTTPException(status_code=422, detail="供应商状态没有发生变化")
    selected = month_date(payload.change_month)
    ensure_month_editable(db, selected)
    target.is_active = payload.is_active
    target.updated_by_id = user.id
    change_type = "activated" if payload.is_active else "deactivated"
    add_change(
        db,
        target,
        change_month=selected,
        change_type=change_type,
        change_note=payload.change_note,
        user=user,
    )
    sync_supplier_metric(db, selected, user)
    add_audit_log(
        db,
        action=f"supplier_{change_type}",
        resource=f"supplier:{target.id}",
        request=request,
        user=user,
        detail={"name": target.name, "change_month": payload.change_month},
    )
    db.commit()
    return serialize_supplier(target)
