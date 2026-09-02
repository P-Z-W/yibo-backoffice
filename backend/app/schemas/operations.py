"""Schemas for migrated operational modules."""

from decimal import Decimal
from typing import Literal

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
    highlights: str = ""
    issues: str = ""
    risks: str = ""
    next_plan: str = ""


class MonthlyAnalyticsStatusInput(BaseModel):
    month: str = Field(pattern=r"^\d{4}-\d{2}$")
    status: Literal["draft", "completed", "archived"]


class ShippingRemarkInput(BaseModel):
    month: str = Field(pattern=r"^\d{4}-\d{2}$")
    remark: str = Field(default="", max_length=500)


class StaffingAnalysisInput(BaseModel):
    month: str = Field(pattern=r"^\d{4}-\d{2}$")
    analysis: str = Field(default="", max_length=5000)


class StaffingInputsInput(BaseModel):
    month: str = Field(pattern=r"^\d{4}-\d{2}$")
    team_name: str | None = Field(default=None, max_length=100)
    regular_staff: Decimal = Field(ge=0, le=1000000, decimal_places=2)
    optimal_staff: Decimal | None = Field(default=None, ge=0, le=1000000, decimal_places=2)
    monthly_output: Decimal | None = Field(
        default=None, ge=0, le=1000000000, decimal_places=2
    )
    optimal_monthly_output: Decimal | None = Field(
        default=None, ge=0, le=1000000000, decimal_places=2
    )


class ShippingExportInput(BaseModel):
    month: str = Field(pattern=r"^\d{4}-\d{2}$")
    scope: Literal["filtered", "selected"] = "filtered"
    row_ids: list[int] = Field(default_factory=list, max_length=5000)
    columns: list[
        Literal["团队名称", "发货单量", "数据发货占比", "备注"]
    ] = Field(min_length=1, max_length=4)
    search: str = Field(default="", max_length=100)
    sort_order: Literal["", "asc", "desc"] = ""
