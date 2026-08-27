"""Database-backed operating-analysis APIs."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.analytics import BusinessEvent, MetricDefinition, MonthlyMetric, MonthlyReview
from app.models.user import User
from app.schemas.operations import MonthlyAnalyticsInput

router = APIRouter(prefix="/analytics", tags=["经营分析"])


def month_date(month: str) -> date:
    try:
        return date.fromisoformat(f"{month}-01")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="月份格式必须为 YYYY-MM") from exc


def previous_month(value: date) -> date:
    if value.month == 1:
        return date(value.year - 1, 12, 1)
    return date(value.year, value.month - 1, 1)


@router.get("")
def analytics(
    month: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
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
            }
        )
    review = db.scalar(select(MonthlyReview).where(MonthlyReview.month == selected))
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
            "summary": review.summary if review else "",
            "status": review.status if review else "draft",
        },
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
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict[str, object]:
    selected = month_date(payload.month)
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
        if target is None:
            target = MonthlyMetric(metric_id=item.metric_id, month=selected, value=item.value)
            db.add(target)
        else:
            target.value = Decimal(item.value)
        target.note = item.note.strip() or None
    review = db.scalar(select(MonthlyReview).where(MonthlyReview.month == selected))
    if review is None:
        review = MonthlyReview(month=selected, summary=payload.summary, status="draft")
        db.add(review)
    else:
        review.summary = payload.summary
    db.commit()
    return {"ok": True, "message": f"{payload.month} 经营数据已保存"}
