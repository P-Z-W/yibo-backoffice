"""Operating-analysis detail import tests."""

from datetime import date
from io import BytesIO

from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy import delete, select

from app.core.config import settings
from app.db.session import SessionLocal
from app.main import app
from app.models.analytics import (
    AnalyticsDetailRow,
    AnalyticsImportBatch,
    MetricDefinition,
    MonthlyMetric,
    MonthlyReview,
)
from app.models.user import AuditLog


def workbook_bytes(values: tuple[int, int]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "1-发货单量"
    sheet.append(["月份", "团队名称", "发货单量", "备注"])
    sheet.append(["2031-01", "测试一组", values[0], "人工上传"])
    sheet.append(["2031-01", "测试二组", values[1], "人工上传"])
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def login(client: TestClient) -> None:
    response = client.post(
        f"{settings.api_prefix}/auth/login",
        json={
            "username": settings.initial_admin_username,
            "password": settings.initial_admin_password,
        },
    )
    assert response.status_code == 200


def cleanup_test_month() -> None:
    selected = date(2031, 1, 1)
    with SessionLocal() as db:
        batch_ids = list(
            db.scalars(
                select(AnalyticsImportBatch.id).where(
                    AnalyticsImportBatch.dataset_type == "shipping_orders",
                    AnalyticsImportBatch.month == selected,
                )
            )
        )
        if batch_ids:
            db.execute(
                delete(AnalyticsDetailRow).where(AnalyticsDetailRow.batch_id.in_(batch_ids))
            )
            db.execute(
                delete(AnalyticsImportBatch).where(AnalyticsImportBatch.id.in_(batch_ids))
            )
        metric_id = db.scalar(
            select(MetricDefinition.id).where(MetricDefinition.code == "shipping_orders")
        )
        if metric_id is not None:
            db.execute(
                delete(MonthlyMetric).where(
                    MonthlyMetric.metric_id == metric_id,
                    MonthlyMetric.month == selected,
                )
            )
        db.execute(
            delete(AuditLog).where(
                AuditLog.resource.in_(
                    ["analytics:shipping_orders:2031-01", "analytics:2031-01"]
                )
            )
        )
        db.execute(delete(MonthlyReview).where(MonthlyReview.month == selected))
        db.commit()


def test_analytics_detail_preview_import_and_replace() -> None:
    cleanup_test_month()
    try:
        with TestClient(app) as client:
            login(client)
            first_file = workbook_bytes((10, 20))
            preview = client.post(
                f"{settings.api_prefix}/analytics/details/shipping_orders/preview",
                files={"file": ("经营分析.xlsx", first_file, "application/vnd.ms-excel")},
            )
            assert preview.status_code == 200
            assert preview.json()["row_count"] == 2
            assert preview.json()["summary"]["shipping_orders"] == 30

            imported = client.post(
                f"{settings.api_prefix}/analytics/details/shipping_orders/import",
                data={"month": "2031-01", "mode": "replace"},
                files={"file": ("经营分析.xlsx", first_file, "application/vnd.ms-excel")},
            )
            assert imported.status_code == 200
            assert imported.json()["updated_metrics"][0]["value"] == 30

            replacement = workbook_bytes((2, 3))
            replaced = client.post(
                f"{settings.api_prefix}/analytics/details/shipping_orders/import",
                data={"month": "2031-01", "mode": "replace"},
                files={"file": ("替换.xlsx", replacement, "application/vnd.ms-excel")},
            )
            assert replaced.status_code == 200
            assert replaced.json()["updated_metrics"][0]["value"] == 5

            details = client.get(
                f"{settings.api_prefix}/analytics/details/shipping_orders",
                params={"month": "2031-01"},
            )
            assert details.status_code == 200
            assert details.json()["total"] == 2
            assert details.json()["summary"]["shipping_orders"] == 5
            assert details.json()["batches"][0]["original_name"] == "替换.xlsx"

            analytics = client.get(
                f"{settings.api_prefix}/analytics", params={"month": "2031-01"}
            )
            assert analytics.status_code == 200
            shipping = next(
                item for item in analytics.json()["metrics"] if item["code"] == "shipping_orders"
            )
            assert shipping["value"] == 5
            assert shipping["source_type"] == "excel"
            shipping_completion = next(
                item
                for item in analytics.json()["completion"]["items"]
                if item["code"] == "shipping_orders"
            )
            assert shipping_completion["state"] == "uploaded"

            template = client.get(
                f"{settings.api_prefix}/analytics/details/shipping_orders/template"
            )
            assert template.status_code == 200
            assert template.headers["content-type"].startswith(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    finally:
        cleanup_test_month()


def test_lightweight_monthly_review_and_archive_lock() -> None:
    cleanup_test_month()
    try:
        with TestClient(app) as client:
            login(client)
            initial = client.get(
                f"{settings.api_prefix}/analytics", params={"month": "2031-01"}
            )
            assert initial.status_code == 200
            shipping = next(
                item for item in initial.json()["metrics"] if item["code"] == "shipping_orders"
            )
            saved = client.put(
                f"{settings.api_prefix}/analytics",
                json={
                    "month": "2031-01",
                    "metrics": [
                        {"metric_id": shipping["id"], "value": 42, "note": "测试说明"}
                    ],
                    "summary": "整体平稳",
                    "highlights": "发货效率提升",
                    "issues": "人工登记仍较多",
                    "risks": "数据口径待统一",
                    "next_plan": "完成模板培训",
                },
            )
            assert saved.status_code == 200

            analytics = client.get(
                f"{settings.api_prefix}/analytics", params={"month": "2031-01"}
            ).json()
            assert analytics["review"]["highlights"] == "发货效率提升"
            assert analytics["review"]["next_plan"] == "完成模板培训"
            assert analytics["latest_activity"]["updated_by_name"] == "系统管理员"
            shipping = next(
                item for item in analytics["metrics"] if item["code"] == "shipping_orders"
            )
            assert shipping["source_type"] == "manual"
            shipping_completion = next(
                item
                for item in analytics["completion"]["items"]
                if item["code"] == "shipping_orders"
            )
            assert shipping_completion["state"] == "summary_only"

            completed = client.put(
                f"{settings.api_prefix}/analytics/status",
                json={"month": "2031-01", "status": "completed"},
            )
            assert completed.status_code == 200
            archived = client.put(
                f"{settings.api_prefix}/analytics/status",
                json={"month": "2031-01", "status": "archived"},
            )
            assert archived.status_code == 200

            locked = client.put(
                f"{settings.api_prefix}/analytics",
                json={
                    "month": "2031-01",
                    "metrics": [],
                    "summary": "不应保存",
                    "highlights": "",
                    "issues": "",
                    "risks": "",
                    "next_plan": "",
                },
            )
            assert locked.status_code == 409

            reopened = client.put(
                f"{settings.api_prefix}/analytics/status",
                json={"month": "2031-01", "status": "draft"},
            )
            assert reopened.status_code == 200
            assert reopened.json()["status"] == "draft"
    finally:
        cleanup_test_month()
