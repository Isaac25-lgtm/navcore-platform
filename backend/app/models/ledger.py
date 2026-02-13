from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import LedgerEntryType


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        default=1,
    )
    club_id: Mapped[int] = mapped_column(ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False)
    period_id: Mapped[int] = mapped_column(
        ForeignKey("accounting_periods.id", ondelete="CASCADE"), nullable=False
    )
    investor_id: Mapped[int | None] = mapped_column(
        ForeignKey("investors.id", ondelete="SET NULL"),
        nullable=True,
    )

    entry_type: Mapped[LedgerEntryType] = mapped_column(
        Enum(LedgerEntryType, name="ledger_entry_type"),
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(24, 2), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False, default="general")
    tx_date: Mapped[date] = mapped_column(nullable=False, server_default=func.current_date())
    description: Mapped[str] = mapped_column(Text, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    attachment_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    created_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    club: Mapped["Club"] = relationship("Club", back_populates="ledger_entries")
    period: Mapped["AccountingPeriod"] = relationship("AccountingPeriod", back_populates="ledger_entries")
    investor: Mapped["Investor | None"] = relationship("Investor", back_populates="ledger_entries")
    created_by_user: Mapped["User"] = relationship("User", back_populates="ledger_entries")
