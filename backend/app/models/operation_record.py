"""Structured monthly records for customer and operating modules."""

from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CustomerChangeRecord(Base):
    __tablename__ = "customer_change_records"
    __table_args__ = (
        Index("ix_customer_change_month_type", "month", "change_type"),
        Index("ix_customer_change_month_customer", "month", "customer_name"),
        Index("ix_customer_change_occurred_at", "occurred_at"),
        Index("ux_customer_change_source_team", "source_team_id", unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    month: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    source_team_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    change_type: Mapped[str] = mapped_column(String(20), index=True)
    customer_name: Mapped[str] = mapped_column(String(160), default="")
    source_channel: Mapped[str] = mapped_column(String(100), default="")
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    updated_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class CustomerServiceRecord(Base):
    __tablename__ = "customer_service_records"
    __table_args__ = (
        Index("ix_customer_service_month_status", "month", "status"),
        Index("ix_customer_service_month_team", "month", "team_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    month: Mapped[date] = mapped_column(Date, index=True)
    team_name: Mapped[str] = mapped_column(String(160), default="")
    complaint_category: Mapped[str] = mapped_column(String(120), default="")
    issue_description: Mapped[str] = mapped_column(Text)
    verified_cause: Mapped[str | None] = mapped_column(Text, nullable=True)
    responsibility: Mapped[str] = mapped_column(String(160), default="")
    corrective_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="待核实", index=True)
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    updated_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class ValueAddedRecord(Base):
    __tablename__ = "value_added_records"
    __table_args__ = (
        Index("ix_value_added_month_team", "month", "team_name"),
        Index("ix_value_added_month_service", "month", "service_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    month: Mapped[date] = mapped_column(Date, index=True)
    team_id: Mapped[str] = mapped_column(String(80), default="")
    team_name: Mapped[str] = mapped_column(String(160), default="")
    service_code: Mapped[str] = mapped_column(String(80), default="")
    service_name: Mapped[str] = mapped_column(String(160), default="")
    service_group: Mapped[str] = mapped_column(String(100), default="")
    quantity: Mapped[int] = mapped_column(Integer, default=0)
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    updated_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class ShortVideoRecord(Base):
    __tablename__ = "short_video_records"
    __table_args__ = (Index("ix_short_video_month_type", "month", "video_type"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    month: Mapped[date] = mapped_column(Date, index=True)
    video_count: Mapped[int] = mapped_column(Integer, default=0)
    video_type: Mapped[str] = mapped_column(String(120), default="")
    owner: Mapped[str] = mapped_column(String(100), default="")
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    updated_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
