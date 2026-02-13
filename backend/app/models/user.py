from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Enum, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import RoleName


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[RoleName] = mapped_column(
        Enum(RoleName, name="role_name"),
        default=RoleName.viewer,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    memberships: Mapped[list["ClubMembership"]] = relationship(
        "ClubMembership", back_populates="user", cascade="all, delete-orphan"
    )
    tenant_roles: Mapped[list["UserRole"]] = relationship(
        "UserRole", back_populates="user", cascade="all, delete-orphan"
    )
    ledger_entries: Mapped[list["LedgerEntry"]] = relationship(
        "LedgerEntry", back_populates="created_by_user"
    )
    closed_periods: Mapped[list["AccountingPeriod"]] = relationship(
        "AccountingPeriod",
        back_populates="closed_by_user",
        foreign_keys="AccountingPeriod.closed_by_user_id",
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship("AuditLog", back_populates="actor_user")
    generated_reports: Mapped[list["ReportSnapshot"]] = relationship(
        "ReportSnapshot", back_populates="generated_by_user"
    )
