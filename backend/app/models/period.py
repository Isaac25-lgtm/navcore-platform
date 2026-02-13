from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import PeriodStatus


class AccountingPeriod(Base):
    __tablename__ = "accounting_periods"
    __table_args__ = (
        UniqueConstraint("club_id", "year", "month", name="uq_periods_club_year_month"),
        UniqueConstraint("club_id", "year_month", name="uq_periods_club_year_month_text"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        default=1,
    )
    club_id: Mapped[int] = mapped_column(ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    year_month: Mapped[str] = mapped_column(default="", nullable=False, index=True)
    status: Mapped[PeriodStatus] = mapped_column(
        Enum(PeriodStatus, name="period_status"),
        default=PeriodStatus.draft,
        nullable=False,
    )

    opening_nav: Mapped[Decimal] = mapped_column(Numeric(24, 2), default=0, nullable=False)
    closing_nav: Mapped[Decimal] = mapped_column(Numeric(24, 2), default=0, nullable=False)
    reconciliation_diff: Mapped[Decimal] = mapped_column(Numeric(24, 2), default=0, nullable=False)

    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    club: Mapped["Club"] = relationship("Club", back_populates="periods")
    tenant: Mapped["Tenant"] = relationship("Tenant")
    closed_by_user: Mapped["User | None"] = relationship(
        "User",
        back_populates="closed_periods",
        foreign_keys=[closed_by_user_id],
    )
    ledger_entries: Mapped[list["LedgerEntry"]] = relationship(
        "LedgerEntry", back_populates="period", cascade="all, delete-orphan"
    )
    investor_positions: Mapped[list["InvestorPosition"]] = relationship(
        "InvestorPosition", back_populates="period", cascade="all, delete-orphan"
    )
    reports: Mapped[list["ReportSnapshot"]] = relationship("ReportSnapshot", back_populates="period")
    nav_snapshot: Mapped["NavSnapshot | None"] = relationship(
        "NavSnapshot",
        back_populates="period",
        uselist=False,
    )
    balance_snapshots: Mapped[list["InvestorBalance"]] = relationship(
        "InvestorBalance",
        back_populates="period",
    )


class InvestorPosition(Base):
    __tablename__ = "investor_positions"
    __table_args__ = (
        UniqueConstraint("period_id", "investor_id", name="uq_positions_period_investor"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    period_id: Mapped[int] = mapped_column(
        ForeignKey("accounting_periods.id", ondelete="CASCADE"),
        nullable=False,
    )
    investor_id: Mapped[int] = mapped_column(
        ForeignKey("investors.id", ondelete="CASCADE"),
        nullable=False,
    )

    opening_balance: Mapped[Decimal] = mapped_column(Numeric(24, 2), default=0, nullable=False)
    ownership_pct: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=0, nullable=False)
    contributions: Mapped[Decimal] = mapped_column(Numeric(24, 2), default=0, nullable=False)
    withdrawals: Mapped[Decimal] = mapped_column(Numeric(24, 2), default=0, nullable=False)
    income_alloc: Mapped[Decimal] = mapped_column(Numeric(24, 2), default=0, nullable=False)
    expense_alloc: Mapped[Decimal] = mapped_column(Numeric(24, 2), default=0, nullable=False)
    net_allocation: Mapped[Decimal] = mapped_column(Numeric(24, 2), default=0, nullable=False)
    closing_balance: Mapped[Decimal] = mapped_column(Numeric(24, 2), default=0, nullable=False)

    period: Mapped["AccountingPeriod"] = relationship("AccountingPeriod", back_populates="investor_positions")
    investor: Mapped["Investor"] = relationship("Investor", back_populates="positions")
