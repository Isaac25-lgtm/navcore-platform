from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class NavSnapshot(Base):
    __tablename__ = "nav_snapshots"
    __table_args__ = (
        UniqueConstraint("club_id", "period_id", name="uq_nav_snapshot_club_period"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    club_id: Mapped[int] = mapped_column(ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False, index=True)
    period_id: Mapped[int] = mapped_column(
        ForeignKey("accounting_periods.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    opening_nav: Mapped[Decimal] = mapped_column(Numeric(24, 2), nullable=False)
    contributions_total: Mapped[Decimal] = mapped_column(Numeric(24, 2), nullable=False)
    withdrawals_total: Mapped[Decimal] = mapped_column(Numeric(24, 2), nullable=False)
    income_total: Mapped[Decimal] = mapped_column(Numeric(24, 2), nullable=False)
    expenses_total: Mapped[Decimal] = mapped_column(Numeric(24, 2), nullable=False)
    closing_nav: Mapped[Decimal] = mapped_column(Numeric(24, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    club: Mapped["Club"] = relationship("Club", back_populates="nav_snapshots")
    period: Mapped["AccountingPeriod"] = relationship("AccountingPeriod", back_populates="nav_snapshot")
    investor_balances: Mapped[list["InvestorBalance"]] = relationship(
        "InvestorBalance",
        back_populates="snapshot",
        cascade="all, delete-orphan",
    )


class InvestorBalance(Base):
    __tablename__ = "investor_balances"
    __table_args__ = (
        UniqueConstraint("period_id", "investor_id", name="uq_investor_balances_period_investor"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    club_id: Mapped[int] = mapped_column(ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False, index=True)
    investor_id: Mapped[int] = mapped_column(ForeignKey("investors.id", ondelete="CASCADE"), nullable=False, index=True)
    period_id: Mapped[int] = mapped_column(ForeignKey("accounting_periods.id", ondelete="CASCADE"), nullable=False, index=True)
    snapshot_id: Mapped[int] = mapped_column(ForeignKey("nav_snapshots.id", ondelete="CASCADE"), nullable=False, index=True)

    opening_balance: Mapped[Decimal] = mapped_column(Numeric(24, 2), nullable=False)
    ownership_pct: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    income_alloc: Mapped[Decimal] = mapped_column(Numeric(24, 2), nullable=False)
    expense_alloc: Mapped[Decimal] = mapped_column(Numeric(24, 2), nullable=False)
    net_alloc: Mapped[Decimal] = mapped_column(Numeric(24, 2), nullable=False)
    contributions: Mapped[Decimal] = mapped_column(Numeric(24, 2), nullable=False)
    withdrawals: Mapped[Decimal] = mapped_column(Numeric(24, 2), nullable=False)
    closing_balance: Mapped[Decimal] = mapped_column(Numeric(24, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    investor: Mapped["Investor"] = relationship("Investor", back_populates="balance_snapshots")
    period: Mapped["AccountingPeriod"] = relationship("AccountingPeriod", back_populates="balance_snapshots")
    snapshot: Mapped["NavSnapshot"] = relationship("NavSnapshot", back_populates="investor_balances")
