"""Initial schema for NAV fund platform.

Revision ID: 20260213_0001
Revises:
Create Date: 2026-02-13 18:45:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260213_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    role_name = sa.Enum("admin", "manager", "analyst", "viewer", name="role_name")
    period_status = sa.Enum("draft", "review", "closed", name="period_status")
    ledger_entry_type = sa.Enum(
        "contribution", "withdrawal", "income", "expense", "adjustment", name="ledger_entry_type"
    )
    report_type = sa.Enum("monthly_club", "investor_statement", name="report_type")

    role_name.create(op.get_bind(), checkfirst=True)
    period_status.create(op.get_bind(), checkfirst=True)
    ledger_entry_type.create(op.get_bind(), checkfirst=True)
    report_type.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "clubs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("currency", sa.String(length=10), nullable=False, server_default="UGX"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_clubs_id", "clubs", ["id"])
    op.create_index("ix_clubs_code", "clubs", ["code"], unique=True)

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("role", role_name, nullable=False, server_default="viewer"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_users_id", "users", ["id"])
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "club_memberships",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("club_id", sa.Integer(), sa.ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "club_id", name="uq_club_memberships_user_club"),
    )

    op.create_table(
        "investors",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("club_id", sa.Integer(), sa.ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("investor_code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("club_id", "investor_code", name="uq_investors_club_code"),
    )
    op.create_index("ix_investors_id", "investors", ["id"])

    op.create_table(
        "accounting_periods",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("club_id", sa.Integer(), sa.ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("status", period_status, nullable=False, server_default="draft"),
        sa.Column("opening_nav", sa.Numeric(24, 2), nullable=False, server_default="0"),
        sa.Column("closing_nav", sa.Numeric(24, 2), nullable=False, server_default="0"),
        sa.Column("reconciliation_diff", sa.Numeric(24, 2), nullable=False, server_default="0"),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "closed_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("club_id", "year", "month", name="uq_periods_club_year_month"),
    )
    op.create_index("ix_accounting_periods_id", "accounting_periods", ["id"])

    op.create_table(
        "investor_positions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "period_id",
            sa.Integer(),
            sa.ForeignKey("accounting_periods.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("investor_id", sa.Integer(), sa.ForeignKey("investors.id", ondelete="CASCADE"), nullable=False),
        sa.Column("opening_balance", sa.Numeric(24, 2), nullable=False, server_default="0"),
        sa.Column("ownership_pct", sa.Numeric(12, 6), nullable=False, server_default="0"),
        sa.Column("contributions", sa.Numeric(24, 2), nullable=False, server_default="0"),
        sa.Column("withdrawals", sa.Numeric(24, 2), nullable=False, server_default="0"),
        sa.Column("net_allocation", sa.Numeric(24, 2), nullable=False, server_default="0"),
        sa.Column("closing_balance", sa.Numeric(24, 2), nullable=False, server_default="0"),
        sa.UniqueConstraint("period_id", "investor_id", name="uq_positions_period_investor"),
    )
    op.create_index("ix_investor_positions_id", "investor_positions", ["id"])

    op.create_table(
        "ledger_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("club_id", sa.Integer(), sa.ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "period_id",
            sa.Integer(),
            sa.ForeignKey("accounting_periods.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("investor_id", sa.Integer(), sa.ForeignKey("investors.id", ondelete="SET NULL"), nullable=True),
        sa.Column("entry_type", ledger_entry_type, nullable=False),
        sa.Column("amount", sa.Numeric(24, 2), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("reference", sa.String(length=100), nullable=True),
        sa.Column(
            "created_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_ledger_entries_id", "ledger_entries", ["id"])

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("club_id", sa.Integer(), sa.ForeignKey("clubs.id", ondelete="SET NULL"), nullable=True),
        sa.Column(
            "period_id",
            sa.Integer(),
            sa.ForeignKey("accounting_periods.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "actor_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("entity_type", sa.String(length=100), nullable=False),
        sa.Column("entity_id", sa.String(length=100), nullable=False),
        sa.Column("before_state", sa.JSON(), nullable=True),
        sa.Column("after_state", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_audit_logs_id", "audit_logs", ["id"])

    op.create_table(
        "report_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("club_id", sa.Integer(), sa.ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "period_id",
            sa.Integer(),
            sa.ForeignKey("accounting_periods.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("investor_id", sa.Integer(), sa.ForeignKey("investors.id", ondelete="SET NULL"), nullable=True),
        sa.Column("report_type", report_type, nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("file_path", sa.String(length=1024), nullable=False),
        sa.Column("file_hash", sa.String(length=128), nullable=False),
        sa.Column(
            "generated_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_report_snapshots_id", "report_snapshots", ["id"])


def downgrade() -> None:
    op.drop_index("ix_report_snapshots_id", table_name="report_snapshots")
    op.drop_table("report_snapshots")
    op.drop_index("ix_audit_logs_id", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_index("ix_ledger_entries_id", table_name="ledger_entries")
    op.drop_table("ledger_entries")
    op.drop_index("ix_investor_positions_id", table_name="investor_positions")
    op.drop_table("investor_positions")
    op.drop_index("ix_accounting_periods_id", table_name="accounting_periods")
    op.drop_table("accounting_periods")
    op.drop_index("ix_investors_id", table_name="investors")
    op.drop_table("investors")
    op.drop_table("club_memberships")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_users_id", table_name="users")
    op.drop_table("users")
    op.drop_index("ix_clubs_code", table_name="clubs")
    op.drop_index("ix_clubs_id", table_name="clubs")
    op.drop_table("clubs")

    report_type = sa.Enum("monthly_club", "investor_statement", name="report_type")
    ledger_entry_type = sa.Enum(
        "contribution", "withdrawal", "income", "expense", "adjustment", name="ledger_entry_type"
    )
    period_status = sa.Enum("draft", "review", "closed", name="period_status")
    role_name = sa.Enum("admin", "manager", "analyst", "viewer", name="role_name")

    report_type.drop(op.get_bind(), checkfirst=True)
    ledger_entry_type.drop(op.get_bind(), checkfirst=True)
    period_status.drop(op.get_bind(), checkfirst=True)
    role_name.drop(op.get_bind(), checkfirst=True)

