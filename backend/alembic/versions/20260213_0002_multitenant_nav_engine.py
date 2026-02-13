"""Expand schema for multi-tenant NAV engine and immutable snapshots.

Revision ID: 20260213_0002
Revises: 20260213_0001
Create Date: 2026-02-13 23:30:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260213_0002"
down_revision: Union[str, None] = "20260213_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # extend existing role enum
    op.execute("ALTER TYPE role_name ADD VALUE IF NOT EXISTS 'fund_accountant'")
    op.execute("ALTER TYPE role_name ADD VALUE IF NOT EXISTS 'advisor'")
    op.execute("ALTER TYPE role_name ADD VALUE IF NOT EXISTS 'investor'")

    op.create_table(
        "tenants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_tenants_id", "tenants", ["id"])
    op.create_index("ix_tenants_code", "tenants", ["code"], unique=True)

    op.execute(
        "INSERT INTO tenants (id, code, name, is_active) VALUES (1, 'NAVFUND', 'NAVFund Operator', true)"
    )

    op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=False, server_default=""),
    )
    op.create_index("ix_roles_id", "roles", ["id"])
    op.create_index("ix_roles_name", "roles", ["name"], unique=True)

    op.create_table(
        "user_roles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role_id", sa.Integer(), sa.ForeignKey("roles.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "user_id", "role_id", name="uq_user_roles_tenant_user_role"),
    )
    op.create_index("ix_user_roles_id", "user_roles", ["id"])

    op.execute(
        "INSERT INTO roles (id, name, description) VALUES "
        "(1, 'admin', 'Admin'), "
        "(2, 'fund_accountant', 'Fund Accountant'), "
        "(3, 'advisor', 'Advisor'), "
        "(4, 'investor', 'Investor')"
    )

    # tenant columns across mutable/immutable tables
    for table_name in [
        "clubs",
        "investors",
        "club_memberships",
        "accounting_periods",
        "ledger_entries",
        "report_snapshots",
        "audit_logs",
    ]:
        op.add_column(table_name, sa.Column("tenant_id", sa.Integer(), nullable=False, server_default="1"))
        op.create_foreign_key(
            f"fk_{table_name}_tenant_id",
            table_name,
            "tenants",
            ["tenant_id"],
            ["id"],
            ondelete="CASCADE",
        )
        op.create_index(f"ix_{table_name}_tenant_id", table_name, ["tenant_id"])

    # clubs uniqueness becomes tenant-scoped
    op.drop_index("ix_clubs_code", table_name="clubs")
    op.create_unique_constraint("uq_clubs_tenant_code", "clubs", ["tenant_id", "code"])

    # memberships support investor-club membership while keeping user-club access
    op.alter_column("club_memberships", "user_id", existing_type=sa.Integer(), nullable=True)
    op.add_column("club_memberships", sa.Column("investor_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_club_memberships_investor_id",
        "club_memberships",
        "investors",
        ["investor_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_unique_constraint(
        "uq_club_memberships_investor_club",
        "club_memberships",
        ["investor_id", "club_id"],
    )
    op.create_check_constraint(
        "ck_club_memberships_actor_present",
        "club_memberships",
        "(user_id IS NOT NULL) OR (investor_id IS NOT NULL)",
    )

    # period year_month and tenant-aware uniqueness
    op.add_column(
        "accounting_periods",
        sa.Column("year_month", sa.String(length=7), nullable=False, server_default="1970-01"),
    )
    op.execute(
        "UPDATE accounting_periods SET year_month = CAST(year AS TEXT) || '-' || LPAD(CAST(month AS TEXT), 2, '0')"
    )
    op.create_index("ix_accounting_periods_year_month", "accounting_periods", ["year_month"])
    op.create_unique_constraint(
        "uq_periods_club_year_month_text",
        "accounting_periods",
        ["club_id", "year_month"],
    )

    # ledger transaction metadata
    op.add_column("ledger_entries", sa.Column("category", sa.String(length=100), nullable=False, server_default="general"))
    op.add_column("ledger_entries", sa.Column("tx_date", sa.Date(), nullable=False, server_default=sa.func.current_date()))
    op.add_column("ledger_entries", sa.Column("note", sa.Text(), nullable=True))
    op.add_column("ledger_entries", sa.Column("attachment_url", sa.String(length=1000), nullable=True))

    # investor explainability fields in mutable period positions
    op.add_column("investor_positions", sa.Column("income_alloc", sa.Numeric(24, 2), nullable=False, server_default="0"))
    op.add_column("investor_positions", sa.Column("expense_alloc", sa.Numeric(24, 2), nullable=False, server_default="0"))

    # immutable close snapshots
    op.create_table(
        "nav_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("club_id", sa.Integer(), sa.ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("period_id", sa.Integer(), sa.ForeignKey("accounting_periods.id", ondelete="CASCADE"), nullable=False),
        sa.Column("opening_nav", sa.Numeric(24, 2), nullable=False),
        sa.Column("contributions_total", sa.Numeric(24, 2), nullable=False),
        sa.Column("withdrawals_total", sa.Numeric(24, 2), nullable=False),
        sa.Column("income_total", sa.Numeric(24, 2), nullable=False),
        sa.Column("expenses_total", sa.Numeric(24, 2), nullable=False),
        sa.Column("closing_nav", sa.Numeric(24, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("club_id", "period_id", name="uq_nav_snapshot_club_period"),
    )
    op.create_index("ix_nav_snapshots_id", "nav_snapshots", ["id"])
    op.create_index("ix_nav_snapshots_tenant_id", "nav_snapshots", ["tenant_id"])
    op.create_index("ix_nav_snapshots_club_id", "nav_snapshots", ["club_id"])
    op.create_index("ix_nav_snapshots_period_id", "nav_snapshots", ["period_id"])

    op.create_table(
        "investor_balances",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("club_id", sa.Integer(), sa.ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("investor_id", sa.Integer(), sa.ForeignKey("investors.id", ondelete="CASCADE"), nullable=False),
        sa.Column("period_id", sa.Integer(), sa.ForeignKey("accounting_periods.id", ondelete="CASCADE"), nullable=False),
        sa.Column("snapshot_id", sa.Integer(), sa.ForeignKey("nav_snapshots.id", ondelete="CASCADE"), nullable=False),
        sa.Column("opening_balance", sa.Numeric(24, 2), nullable=False),
        sa.Column("ownership_pct", sa.Numeric(12, 6), nullable=False),
        sa.Column("income_alloc", sa.Numeric(24, 2), nullable=False),
        sa.Column("expense_alloc", sa.Numeric(24, 2), nullable=False),
        sa.Column("net_alloc", sa.Numeric(24, 2), nullable=False),
        sa.Column("contributions", sa.Numeric(24, 2), nullable=False),
        sa.Column("withdrawals", sa.Numeric(24, 2), nullable=False),
        sa.Column("closing_balance", sa.Numeric(24, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("period_id", "investor_id", name="uq_investor_balances_period_investor"),
    )
    op.create_index("ix_investor_balances_id", "investor_balances", ["id"])
    op.create_index("ix_investor_balances_tenant_id", "investor_balances", ["tenant_id"])
    op.create_index("ix_investor_balances_club_id", "investor_balances", ["club_id"])
    op.create_index("ix_investor_balances_investor_id", "investor_balances", ["investor_id"])
    op.create_index("ix_investor_balances_period_id", "investor_balances", ["period_id"])
    op.create_index("ix_investor_balances_snapshot_id", "investor_balances", ["snapshot_id"])


def downgrade() -> None:
    op.drop_index("ix_investor_balances_snapshot_id", table_name="investor_balances")
    op.drop_index("ix_investor_balances_period_id", table_name="investor_balances")
    op.drop_index("ix_investor_balances_investor_id", table_name="investor_balances")
    op.drop_index("ix_investor_balances_club_id", table_name="investor_balances")
    op.drop_index("ix_investor_balances_tenant_id", table_name="investor_balances")
    op.drop_index("ix_investor_balances_id", table_name="investor_balances")
    op.drop_table("investor_balances")

    op.drop_index("ix_nav_snapshots_period_id", table_name="nav_snapshots")
    op.drop_index("ix_nav_snapshots_club_id", table_name="nav_snapshots")
    op.drop_index("ix_nav_snapshots_tenant_id", table_name="nav_snapshots")
    op.drop_index("ix_nav_snapshots_id", table_name="nav_snapshots")
    op.drop_table("nav_snapshots")

    op.drop_column("investor_positions", "expense_alloc")
    op.drop_column("investor_positions", "income_alloc")

    op.drop_column("ledger_entries", "attachment_url")
    op.drop_column("ledger_entries", "note")
    op.drop_column("ledger_entries", "tx_date")
    op.drop_column("ledger_entries", "category")

    op.drop_constraint("uq_periods_club_year_month_text", "accounting_periods", type_="unique")
    op.drop_index("ix_accounting_periods_year_month", table_name="accounting_periods")
    op.drop_column("accounting_periods", "year_month")

    op.drop_constraint("ck_club_memberships_actor_present", "club_memberships", type_="check")
    op.drop_constraint("uq_club_memberships_investor_club", "club_memberships", type_="unique")
    op.drop_constraint("fk_club_memberships_investor_id", "club_memberships", type_="foreignkey")
    op.drop_column("club_memberships", "investor_id")
    op.alter_column("club_memberships", "user_id", existing_type=sa.Integer(), nullable=False)

    op.drop_constraint("uq_clubs_tenant_code", "clubs", type_="unique")
    op.create_index("ix_clubs_code", "clubs", ["code"], unique=True)

    for table_name in [
        "audit_logs",
        "report_snapshots",
        "ledger_entries",
        "accounting_periods",
        "club_memberships",
        "investors",
        "clubs",
    ]:
        op.drop_index(f"ix_{table_name}_tenant_id", table_name=table_name)
        op.drop_constraint(f"fk_{table_name}_tenant_id", table_name, type_="foreignkey")
        op.drop_column(table_name, "tenant_id")

    op.drop_index("ix_user_roles_id", table_name="user_roles")
    op.drop_table("user_roles")
    op.drop_index("ix_roles_name", table_name="roles")
    op.drop_index("ix_roles_id", table_name="roles")
    op.drop_table("roles")
    op.drop_index("ix_tenants_code", table_name="tenants")
    op.drop_index("ix_tenants_id", table_name="tenants")
    op.drop_table("tenants")
