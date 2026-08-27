"""Health and system-overview endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.session import get_db
from app.models.analytics import MetricDefinition, MonthlyMetric, MonthlyReview
from app.models.user import User

router = APIRouter(tags=["系统"])


@router.get("/health")
def health(db: Session = Depends(get_db)) -> dict[str, str]:
    db.execute(text("SELECT 1"))
    return {
        "status": "ok",
        "database": "connected",
        "version": settings.app_version,
    }


@router.get("/system/overview")
def system_overview(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict[str, object]:
    return {
        "version": settings.app_version,
        "database": settings.db_name,
        "modules": [
            {"name": "经营分析", "status": "ready"},
            {"name": "快递对账", "status": "ready"},
            {"name": "数据查询", "status": "ready"},
            {"name": "员工工资", "status": "ready"},
        ],
        "analytics": {
            "metric_definitions": db.scalar(select(func.count(MetricDefinition.id))) or 0,
            "metric_values": db.scalar(select(func.count(MonthlyMetric.id))) or 0,
            "monthly_reviews": db.scalar(select(func.count(MonthlyReview.id))) or 0,
        },
    }
