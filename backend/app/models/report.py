from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import ReportType


class ReportSnapshot(Base):
    __tablename__ = "report_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        default=1,
    )
    club_id: Mapped[int] = mapped_column(ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False)
    period_id: Mapped[int] = mapped_column(
        ForeignKey("accounting_periods.id", ondelete="CASCADE"),
        nullable=False,
    )
    investor_id: Mapped[int | None] = mapped_column(
        ForeignKey("investors.id", ondelete="SET NULL"),
        nullable=True,
    )
    report_type: Mapped[ReportType] = mapped_column(
        Enum(ReportType, name="report_type"),
        nullable=False,
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    generated_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    club: Mapped["Club"] = relationship("Club", back_populates="reports")
    period: Mapped["AccountingPeriod"] = relationship("AccountingPeriod", back_populates="reports")
    investor: Mapped["Investor | None"] = relationship("Investor", back_populates="reports")
    generated_by_user: Mapped["User"] = relationship("User", back_populates="generated_reports")
