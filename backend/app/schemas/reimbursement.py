"""Validation schemas for lightweight reimbursements."""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


class ReimbursementItemInput(BaseModel):
    expense_date: date
    category: str = Field(min_length=1, max_length=60)
    amount: Decimal = Field(ge=0, decimal_places=2, max_digits=12)
    related_number: str = Field(default="", max_length=100)
    description: str = Field(default="", max_length=255)

    @field_validator("category", "related_number", "description", mode="before")
    @classmethod
    def strip_text(cls, value: object) -> str:
        return str(value or "").strip()


class ReimbursementInput(BaseModel):
    applicant_name: str = Field(min_length=1, max_length=80)
    team: str = Field(pattern=r"^(发货组|退货组)$")
    entity_name: str = Field(default="", max_length=160)
    tax_number: str = Field(default="", max_length=32)
    note: str = Field(default="", max_length=1000)
    items: list[ReimbursementItemInput] = Field(min_length=1, max_length=200)

    @field_validator("applicant_name", "entity_name", "note", mode="before")
    @classmethod
    def strip_text(cls, value: object) -> str:
        return str(value or "").strip()

    @field_validator("tax_number", mode="before")
    @classmethod
    def normalize_tax_number(cls, value: object) -> str:
        return "".join(str(value or "").upper().split())


class ReimbursementActionInput(BaseModel):
    comment: str = Field(default="", max_length=500)

    @field_validator("comment", mode="before")
    @classmethod
    def strip_comment(cls, value: object) -> str:
        return str(value or "").strip()


class ReimbursementConfigInput(BaseModel):
    finance_approval_enabled: bool


class ReimbursementExportInput(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=500)


class ReimbursementEntityInput(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    tax_number: str = Field(min_length=1, max_length=32)
    is_default: bool = False
    is_active: bool = True

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, value: object) -> str:
        return str(value or "").strip()

    @field_validator("tax_number", mode="before")
    @classmethod
    def normalize_entity_tax_number(cls, value: object) -> str:
        return "".join(str(value or "").upper().split())


class ReimbursementInvoiceInput(BaseModel):
    entity_name: str = Field(default="", max_length=160)
    tax_number: str = Field(default="", max_length=32)
    amount: Decimal | None = Field(default=None, ge=0, decimal_places=2, max_digits=12)

    @field_validator("entity_name", mode="before")
    @classmethod
    def strip_entity_name(cls, value: object) -> str:
        return str(value or "").strip()

    @field_validator("tax_number", mode="before")
    @classmethod
    def normalize_invoice_tax_number(cls, value: object) -> str:
        return "".join(str(value or "").upper().split())
