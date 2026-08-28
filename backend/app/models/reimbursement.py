"""Lightweight warehouse reimbursement workflow models."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Reimbursement(Base):
    __tablename__ = "reimbursements"
    __table_args__ = (
        Index("ix_reimbursements_team_status", "team", "status"),
        Index("ix_reimbursements_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    number: Mapped[str] = mapped_column(String(24), unique=True, index=True)
    applicant_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    applicant_name: Mapped[str] = mapped_column(String(80))
    team: Mapped[str] = mapped_column(String(40), index=True)
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    finance_approval_required: Mapped[bool] = mapped_column(Boolean, default=False)
    exported: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    export_batch: Mapped[str | None] = mapped_column(String(40), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    supervisor_approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finance_approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    exported_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    items: Mapped[list["ReimbursementItem"]] = relationship(
        back_populates="reimbursement",
        cascade="all, delete-orphan",
        order_by="ReimbursementItem.sort_order",
    )
    attachments: Mapped[list["ReimbursementAttachment"]] = relationship(
        back_populates="reimbursement", cascade="all, delete-orphan"
    )
    approval_records: Mapped[list["ReimbursementApproval"]] = relationship(
        back_populates="reimbursement",
        cascade="all, delete-orphan",
        order_by="ReimbursementApproval.created_at",
    )


class ReimbursementItem(Base):
    __tablename__ = "reimbursement_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    reimbursement_id: Mapped[int] = mapped_column(
        ForeignKey("reimbursements.id", ondelete="CASCADE"), index=True
    )
    expense_date: Mapped[date] = mapped_column(Date)
    category: Mapped[str] = mapped_column(String(60))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    related_number: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    reimbursement: Mapped[Reimbursement] = relationship(back_populates="items")


class ReimbursementAttachment(Base):
    __tablename__ = "reimbursement_attachments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    reimbursement_id: Mapped[int] = mapped_column(
        ForeignKey("reimbursements.id", ondelete="CASCADE"), index=True
    )
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    original_name: Mapped[str] = mapped_column(String(255))
    stored_name: Mapped[str] = mapped_column(String(255))
    relative_path: Mapped[str] = mapped_column(String(500), unique=True)
    content_type: Mapped[str] = mapped_column(String(100), default="application/octet-stream")
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    reimbursement: Mapped[Reimbursement] = relationship(back_populates="attachments")


class ReimbursementApproval(Base):
    __tablename__ = "reimbursement_approvals"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    reimbursement_id: Mapped[int] = mapped_column(
        ForeignKey("reimbursements.id", ondelete="CASCADE"), index=True
    )
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    actor_name: Mapped[str] = mapped_column(String(80))
    actor_role: Mapped[str] = mapped_column(String(32))
    action: Mapped[str] = mapped_column(String(32))
    from_status: Mapped[str] = mapped_column(String(32), default="")
    to_status: Mapped[str] = mapped_column(String(32))
    comment: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    reimbursement: Mapped[Reimbursement] = relationship(back_populates="approval_records")
