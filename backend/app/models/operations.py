"""Operational models migrated from the stable legacy system."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ExpressCarrier(Base):
    __tablename__ = "express_carriers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(40), unique=True)
    identify_column: Mapped[str] = mapped_column(String(80))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class SystemSetting(Base):
    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(String(255), default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class ExpressChargePrice(Base):
    __tablename__ = "express_charge_prices"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    express_type: Mapped[str] = mapped_column(String(20), unique=True)
    charge_price: Mapped[Decimal] = mapped_column(Numeric(8, 3), default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class TeamExpressPrice(Base):
    __tablename__ = "team_express_prices"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    seq: Mapped[int] = mapped_column(Integer, default=0)
    team_name: Mapped[str] = mapped_column(String(100), unique=True)
    st_fee: Mapped[Decimal] = mapped_column(Numeric(8, 3), default=0)
    st_avg: Mapped[Decimal] = mapped_column(Numeric(8, 3), default=0)
    st_extra: Mapped[Decimal] = mapped_column(Numeric(8, 3), default=0)
    zt_fee: Mapped[Decimal] = mapped_column(Numeric(8, 3), default=0)
    zt_avg: Mapped[Decimal] = mapped_column(Numeric(8, 3), default=0)
    zt_extra: Mapped[Decimal] = mapped_column(Numeric(8, 3), default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
    special_rule: Mapped["TeamSpecialRule | None"] = relationship(
        back_populates="team", cascade="all, delete-orphan", uselist=False
    )


class TeamSpecialRule(Base):
    __tablename__ = "team_special_rules"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    team_id: Mapped[int] = mapped_column(
        ForeignKey("team_express_prices.id", ondelete="CASCADE"), unique=True
    )
    xixi_1kg_unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=10)
    special_note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
    team: Mapped[TeamExpressPrice] = relationship(back_populates="special_rule")


class QueryConfig(Base):
    __tablename__ = "query_configs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    group_name: Mapped[str] = mapped_column(String(100), index=True)
    query_name: Mapped[str] = mapped_column(String(100))
    filename: Mapped[str] = mapped_column(String(255), default="")
    sql_content: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class SalaryRecord(Base):
    __tablename__ = "salary_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50))
    team: Mapped[str] = mapped_column(String(50), default="")
    year_month: Mapped[str] = mapped_column(String(7), index=True)
    base_salary: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    bonus: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    deduction: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class JobRun(Base):
    __tablename__ = "job_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    job_type: Mapped[str] = mapped_column(String(40), index=True)
    period: Mapped[str] = mapped_column(String(20), index=True, default="")
    status: Mapped[str] = mapped_column(String(24), index=True, default="pending")
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    elapsed_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class StoredFile(Base):
    __tablename__ = "stored_files"
    __table_args__ = (UniqueConstraint("relative_path", name="uq_stored_file_path"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    category: Mapped[str] = mapped_column(String(40), index=True)
    period: Mapped[str] = mapped_column(String(20), index=True, default="")
    original_name: Mapped[str] = mapped_column(String(255))
    relative_path: Mapped[str] = mapped_column(String(500))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    source: Mapped[str] = mapped_column(String(40), default="legacy")
    file_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
