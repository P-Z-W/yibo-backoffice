"""Schemas for migrated operational modules."""

from decimal import Decimal

from pydantic import BaseModel, Field


class CarrierInput(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    identify_column: str = Field(min_length=1, max_length=80)
    enabled: bool = True


class CarrierListInput(BaseModel):
    carriers: list[CarrierInput]


class ExpressSettingsInput(BaseModel):
    extend_days_before: int = Field(ge=0, le=60)
    extend_days_after: int = Field(ge=0, le=60)


class TeamPriceInput(BaseModel):
    team: str = Field(min_length=1, max_length=100)
    st_fee: Decimal = Decimal("0")
    st3: Decimal = Decimal("0")
    st01: Decimal = Decimal("0")
    zt_fee: Decimal = Decimal("0")
    zt3: Decimal = Decimal("0")
    zt01: Decimal = Decimal("0")
    xixi_1kg_unit_price: Decimal | None = None
    special_note: str = Field(default="", max_length=255)


class TeamPriceListInput(BaseModel):
    rows: list[TeamPriceInput]


class QueryConfigInput(BaseModel):
    group_name: str = Field(min_length=1, max_length=100)
    filename: str = Field(default="", max_length=255)
    sql_content: str = ""


class SalaryInput(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    team: str = Field(default="", max_length=50)
    year_month: str = Field(pattern=r"^\d{4}-\d{2}$")
    base_salary: Decimal = Decimal("0")
    bonus: Decimal = Decimal("0")
    deduction: Decimal = Decimal("0")
    note: str = ""


class MonthlyMetricInput(BaseModel):
    metric_id: int
    value: Decimal
    note: str = ""


class MonthlyAnalyticsInput(BaseModel):
    month: str = Field(pattern=r"^\d{4}-\d{2}$")
    metrics: list[MonthlyMetricInput]
    summary: str = ""
