"""Normalized monthly operating-analysis models."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class MetricDefinition(Base):
    __tablename__ = "metric_definitions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    category: Mapped[str] = mapped_column(String(50), index=True)
    unit: Mapped[str] = mapped_column(String(20), default="")
    precision: Mapped[int] = mapped_column(Integer, default=0)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    monthly_values: Mapped[list["MonthlyMetric"]] = relationship(back_populates="metric")


class MonthlyMetric(Base):
    __tablename__ = "monthly_metrics"
    __table_args__ = (UniqueConstraint("metric_id", "month", name="uq_metric_month"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    metric_id: Mapped[int] = mapped_column(ForeignKey("metric_definitions.id"), index=True)
    month: Mapped[date] = mapped_column(Date, index=True)
    value: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_type: Mapped[str] = mapped_column(String(24), default="migration", index=True)
    source_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_batch_id: Mapped[int | None] = mapped_column(
        ForeignKey("analytics_import_batches.id", ondelete="SET NULL"), nullable=True, index=True
    )
    updated_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    metric: Mapped[MetricDefinition] = relationship(back_populates="monthly_values")


class MonthlyReview(Base):
    __tablename__ = "monthly_reviews"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    month: Mapped[date] = mapped_column(Date, unique=True, index=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    highlights: Mapped[str | None] = mapped_column(Text, nullable=True)
    issues: Mapped[str | None] = mapped_column(Text, nullable=True)
    risks: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_plan: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="draft", index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class BusinessEvent(Base):
    __tablename__ = "business_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    month: Mapped[date] = mapped_column(Date, index=True)
    event_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    category: Mapped[str] = mapped_column(String(50), index=True)
    title: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AnalyticsImportBatch(Base):
    __tablename__ = "analytics_import_batches"
    __table_args__ = (
        Index("ix_analytics_import_dataset_month", "dataset_type", "month", "active"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    dataset_type: Mapped[str] = mapped_column(String(50), index=True)
    month: Mapped[date] = mapped_column(Date, index=True)
    original_name: Mapped[str] = mapped_column(String(255))
    sheet_name: Mapped[str] = mapped_column(String(100), default="")
    mode: Mapped[str] = mapped_column(String(20), default="replace")
    columns: Mapped[list[str]] = mapped_column(JSON)
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    rows: Mapped[list["AnalyticsDetailRow"]] = relationship(
        back_populates="batch", cascade="all, delete-orphan"
    )


class AnalyticsDetailRow(Base):
    __tablename__ = "analytics_detail_rows"
    __table_args__ = (Index("ix_analytics_detail_batch_row", "batch_id", "row_number"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    batch_id: Mapped[int] = mapped_column(
        ForeignKey("analytics_import_batches.id", ondelete="CASCADE"), index=True
    )
    row_number: Mapped[int] = mapped_column(Integer)
    payload: Mapped[dict[str, object]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    batch: Mapped[AnalyticsImportBatch] = relationship(back_populates="rows")
