"""Validation schemas for supplier master data."""

from datetime import date

from pydantic import BaseModel, Field


class SupplierInput(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    contact_name: str = Field(default="", max_length=100)
    contact_phone: str = Field(default="", max_length=50)
    address: str = Field(default="", max_length=255)
    cooperation_start_date: date | None = None
    product_types: str = Field(default="", max_length=500)
    note: str = Field(default="", max_length=1000)
    change_month: str = Field(pattern=r"^\d{4}-\d{2}$")
    change_note: str = Field(default="", max_length=500)


class SupplierStatusInput(BaseModel):
    is_active: bool
    change_month: str = Field(pattern=r"^\d{4}-\d{2}$")
    change_note: str = Field(default="", max_length=500)
