from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Investor(Base):
    __tablename__ = "investors"
    __table_args__ = (
        UniqueConstraint("club_id", "investor_code", name="uq_investors_club_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        default=1,
    )
    club_id: Mapped[int] = mapped_column(ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False)
    investor_code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    club: Mapped["Club"] = relationship("Club", back_populates="investors")
    tenant: Mapped["Tenant"] = relationship("Tenant")
    positions: Mapped[list["InvestorPosition"]] = relationship("InvestorPosition", back_populates="investor")
    ledger_entries: Mapped[list["LedgerEntry"]] = relationship("LedgerEntry", back_populates="investor")
    reports: Mapped[list["ReportSnapshot"]] = relationship("ReportSnapshot", back_populates="investor")
    memberships: Mapped[list["ClubMembership"]] = relationship("ClubMembership", back_populates="investor")
    balance_snapshots: Mapped[list["InvestorBalance"]] = relationship("InvestorBalance", back_populates="investor")
