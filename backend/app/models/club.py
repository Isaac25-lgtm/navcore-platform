from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Club(Base):
    __tablename__ = "clubs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_clubs_tenant_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        default=1,
    )
    code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="UGX", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="clubs")
    memberships: Mapped[list["ClubMembership"]] = relationship(
        "ClubMembership", back_populates="club", cascade="all, delete-orphan"
    )
    investors: Mapped[list["Investor"]] = relationship(
        "Investor", back_populates="club", cascade="all, delete-orphan"
    )
    periods: Mapped[list["AccountingPeriod"]] = relationship(
        "AccountingPeriod", back_populates="club", cascade="all, delete-orphan"
    )
    ledger_entries: Mapped[list["LedgerEntry"]] = relationship("LedgerEntry", back_populates="club")
    reports: Mapped[list["ReportSnapshot"]] = relationship("ReportSnapshot", back_populates="club")
    nav_snapshots: Mapped[list["NavSnapshot"]] = relationship("NavSnapshot", back_populates="club")


class ClubMembership(Base):
    __tablename__ = "club_memberships"
    __table_args__ = (
        UniqueConstraint("user_id", "club_id", name="uq_club_memberships_user_club"),
        UniqueConstraint("investor_id", "club_id", name="uq_club_memberships_investor_club"),
        CheckConstraint(
            "(user_id IS NOT NULL) OR (investor_id IS NOT NULL)",
            name="ck_club_memberships_actor_present",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        default=1,
    )
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    investor_id: Mapped[int | None] = mapped_column(
        ForeignKey("investors.id", ondelete="CASCADE"),
        nullable=True,
    )
    club_id: Mapped[int] = mapped_column(ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    tenant: Mapped["Tenant"] = relationship("Tenant")
    user: Mapped["User | None"] = relationship("User", back_populates="memberships")
    investor: Mapped["Investor | None"] = relationship("Investor", back_populates="memberships")
    club: Mapped["Club"] = relationship("Club", back_populates="memberships")
