"""Validation schemas for structured monthly operation records."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class CustomerChangeInput(BaseModel):
    month: str = Field(pattern=r"^\d{4}-\d{2}$")
    change_type: Literal["新进", "流失", "意向"]
    occurred_at: datetime | None = None
    customer_name: str = Field(default="", max_length=160)
    source_channel: str = Field(default="", max_length=100)
    quantity: int = Field(default=1, ge=0, le=1_000_000)
    note: str = Field(default="", max_length=1000)


class CustomerServiceInput(BaseModel):
    month: str = Field(pattern=r"^\d{4}-\d{2}$")
    team_name: str = Field(default="", max_length=160)
    complaint_category: str = Field(default="", max_length=120)
    issue_description: str = Field(min_length=1, max_length=3000)
    verified_cause: str = Field(default="", max_length=3000)
    responsibility: str = Field(default="", max_length=160)
    corrective_action: str = Field(default="", max_length=3000)
    status: Literal["待核实", "整改中", "已完成", "已关闭"] = "待核实"


class ValueAddedInput(BaseModel):
    month: str = Field(pattern=r"^\d{4}-\d{2}$")
    team_id: str = Field(default="", max_length=80)
    team_name: str = Field(min_length=1, max_length=160)
    service_code: str = Field(default="", max_length=80)
    service_name: str = Field(min_length=1, max_length=160)
    service_group: str = Field(default="", max_length=100)
    quantity: int = Field(ge=0, le=100_000_000)


class ShortVideoInput(BaseModel):
    month: str = Field(pattern=r"^\d{4}-\d{2}$")
    video_count: int = Field(ge=0, le=100_000_000)
    video_type: str = Field(default="", max_length=120)
    owner: str = Field(default="", max_length=100)
    note: str = Field(default="", max_length=1000)
