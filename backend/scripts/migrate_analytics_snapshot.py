"""Import the confirmed numeric history visible in the monthly review sheet."""

from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.analytics import MetricDefinition, MonthlyMetric

VALUES: dict[str, dict[str, int]] = {
    "shipping_orders": {
        "2026-01": 96639,
        "2026-02": 42351,
        "2026-03": 93214,
        "2026-04": 110370,
        "2026-05": 135139,
        "2026-06": 103984,
        "2026-07": 129577,
    },
    "shipping_customer_change": {
        "2026-01": 25,
        "2026-02": 22,
        "2026-03": 28,
        "2026-04": 30,
        "2026-05": 28,
        "2026-06": 30,
        "2026-07": 32,
    },
    "shipping_value_added": {"2026-05": 10193, "2026-06": 9179, "2026-07": 13654},
    "return_items": {
        "2026-01": 68085,
        "2026-02": 18412,
        "2026-03": 66641,
        "2026-04": 80506,
        "2026-05": 116402,
        "2026-06": 101231,
        "2026-07": 130687,
    },
    "return_customer_change": {
        "2026-01": 18,
        "2026-02": 18,
        "2026-03": 26,
        "2026-04": 26,
        "2026-05": 23,
        "2026-06": 24,
        "2026-07": 30,
    },
    "return_value_added": {"2026-05": 35000, "2026-06": 28860, "2026-07": 34508},
    "new_customers": {"2026-03": 5, "2026-04": 1, "2026-05": 2, "2026-06": 3, "2026-07": 2},
    "lost_customers": {"2026-03": 1, "2026-04": 0, "2026-05": 1, "2026-06": 0, "2026-07": 0},
    "prospective_customers": {
        "2026-03": 13,
        "2026-04": 13,
        "2026-05": 9,
        "2026-06": 11,
        "2026-07": 8,
    },
    "supplier_change": {
        "2026-01": 8,
        "2026-02": 8,
        "2026-03": 8,
        "2026-04": 8,
        "2026-05": 9,
        "2026-06": 9,
        "2026-07": 9,
    },
    "staff_adjustment": {
        "2026-01": 26,
        "2026-02": 26,
        "2026-03": 25,
        "2026-04": 25,
        "2026-05": 25,
        "2026-06": 25,
        "2026-07": 25,
    },
}


def main() -> None:
    with SessionLocal() as db:
        definitions = {row.code: row for row in db.scalars(select(MetricDefinition))}
        imported = 0
        for code, months in VALUES.items():
            definition = definitions[code]
            for month, value in months.items():
                month_value = date.fromisoformat(f"{month}-01")
                target = db.scalar(
                    select(MonthlyMetric).where(
                        MonthlyMetric.metric_id == definition.id,
                        MonthlyMetric.month == month_value,
                    )
                )
                if target is None:
                    target = MonthlyMetric(
                        metric_id=definition.id,
                        month=month_value,
                        value=Decimal(value),
                        note="企业微信月度复盘历史迁移",
                    )
                    db.add(target)
                else:
                    target.value = Decimal(value)
                imported += 1
        db.commit()
    print(f"analytics_values={imported}")


if __name__ == "__main__":
    main()
