"""First-version API integration tests."""

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.services import query_jobs


def login(client: TestClient) -> None:
    response = client.post(
        f"{settings.api_prefix}/auth/login",
        json={
            "username": settings.initial_admin_username,
            "password": settings.initial_admin_password,
        },
    )
    assert response.status_code == 200


def test_health_and_login_flow() -> None:
    with TestClient(app) as client:
        health = client.get(f"{settings.api_prefix}/health")
        assert health.status_code == 200
        assert health.json()["database"] == "connected"

        unauthorized = client.get(f"{settings.api_prefix}/auth/me")
        assert unauthorized.status_code == 401

        login(client)

        current = client.get(f"{settings.api_prefix}/auth/me")
        assert current.status_code == 200


def test_migrated_modules_are_readable() -> None:
    with TestClient(app) as client:
        login(client)

        overview = client.get(f"{settings.api_prefix}/system/overview")
        assert overview.status_code == 200
        payload = overview.json()
        assert payload["database"] == "yibo_backoffice"
        assert {item["status"] for item in payload["modules"]} == {"ready"}
        assert payload["analytics"]["metric_definitions"] == 15
        assert payload["analytics"]["metric_values"] == 63

        analytics = client.get(f"{settings.api_prefix}/analytics?month=2026-07")
        assert analytics.status_code == 200
        shipping = next(
            item for item in analytics.json()["metrics"] if item["code"] == "shipping_orders"
        )
        assert shipping["value"] == 129577
        assert shipping["previous_value"] == 103984

        history = client.get(f"{settings.api_prefix}/express/history")
        assert history.status_code == 200
        assert {item["month"] for item in history.json()} >= {
            "2026-05",
            "2026-06",
            "2026-07",
        }

        stats = client.get(f"{settings.api_prefix}/express/stats/2026-07")
        assert stats.status_code == 200
        assert stats.json()["total_orders"] > 0

        configs = client.get(f"{settings.api_prefix}/query-export/configs")
        assert configs.status_code == 200
        assert sum(len(items) for items in configs.json()["groups"].values()) == 4

        salary = client.get(f"{settings.api_prefix}/salary?month=2026-07")
        assert salary.status_code == 200
        assert salary.json()["records"] == []


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM orders",
        "UPDATE orders SET status = 1",
        "SELECT 1; DROP TABLE orders",
    ],
)
def test_query_export_rejects_write_sql(sql: str) -> None:
    with pytest.raises(ValueError):
        query_jobs.validate_read_query(sql)
