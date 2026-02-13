from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.enums import ReportType
from app.models.investor import Investor
from app.models.nav import InvestorBalance
from app.models.period import AccountingPeriod, InvestorPosition
from app.models.report import ReportSnapshot
from app.models.user import User
from app.utils.decimal_math import money


def _hash_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as file_handle:
        while True:
            chunk = file_handle.read(8192)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def _draw_header(pdf: canvas.Canvas, title: str, subtitle: str) -> None:
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(50, 800, title)
    pdf.setFont("Helvetica", 10)
    pdf.drawString(50, 785, subtitle)
    pdf.line(50, 780, 550, 780)


def generate_monthly_club_report(
    db: Session,
    *,
    period: AccountingPeriod,
    club_name: str,
    generated_by: User,
) -> ReportSnapshot:
    settings = get_settings()
    output_dir = Path(settings.reports_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    file_name = f"club-report-{period.club_id}-{period.year:04d}-{period.month:02d}-{timestamp}.pdf"
    file_path = output_dir / file_name

    balance_rows = list(
        db.scalars(
            select(InvestorBalance)
            .where(
                InvestorBalance.period_id == period.id,
                InvestorBalance.club_id == period.club_id,
            )
            .order_by(InvestorBalance.investor_id)
        ).all()
    )
    positions = list(
        db.scalars(
            select(InvestorPosition).where(InvestorPosition.period_id == period.id).order_by(
                InvestorPosition.investor_id
            )
        ).all()
    )
    investors = {
        investor.id: investor
        for investor in db.scalars(
            select(Investor).where(Investor.club_id == period.club_id)
        ).all()
    }

    pdf = canvas.Canvas(str(file_path), pagesize=A4)
    _draw_header(
        pdf,
        f"Monthly Club Report - {club_name}",
        f"Period {period.year:04d}-{period.month:02d} | Status: {period.status.value.upper()}",
    )

    y = 750
    lines = [
        f"Opening NAV: UGX {money(period.opening_nav):,.2f}",
        f"Closing NAV: UGX {money(period.closing_nav):,.2f}",
        f"Reconciliation Diff: UGX {money(period.reconciliation_diff):,.2f}",
    ]
    for line in lines:
        pdf.drawString(50, y, line)
        y -= 16

    y -= 8
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(50, y, "Investor")
    pdf.drawString(220, y, "Opening")
    pdf.drawString(300, y, "Allocation")
    pdf.drawString(390, y, "Contrib/Withdraw")
    pdf.drawString(500, y, "Closing")
    y -= 14
    pdf.setFont("Helvetica", 9)

    rows = []
    if balance_rows:
        rows = [
            {
                "investor_id": row.investor_id,
                "opening_balance": money(row.opening_balance),
                "net_allocation": money(row.net_alloc),
                "contributions": money(row.contributions),
                "withdrawals": money(row.withdrawals),
                "closing_balance": money(row.closing_balance),
            }
            for row in balance_rows
        ]
    else:
        rows = [
            {
                "investor_id": position.investor_id,
                "opening_balance": money(position.opening_balance),
                "net_allocation": money(position.net_allocation),
                "contributions": money(position.contributions),
                "withdrawals": money(position.withdrawals),
                "closing_balance": money(position.closing_balance),
            }
            for position in positions
        ]

    for row in rows:
        investor = investors.get(row["investor_id"])
        if y < 80:
            pdf.showPage()
            y = 800
        contrib_withdraw = money(row["contributions"] - row["withdrawals"])
        pdf.drawString(50, y, investor.name if investor else f"Investor {row['investor_id']}")
        pdf.drawRightString(285, y, f"{money(row['opening_balance']):,.2f}")
        pdf.drawRightString(375, y, f"{money(row['net_allocation']):,.2f}")
        pdf.drawRightString(485, y, f"{contrib_withdraw:,.2f}")
        pdf.drawRightString(550, y, f"{money(row['closing_balance']):,.2f}")
        y -= 14

    pdf.save()

    file_hash = _hash_file(file_path)
    snapshot = ReportSnapshot(
        tenant_id=period.tenant_id,
        club_id=period.club_id,
        period_id=period.id,
        report_type=ReportType.monthly_club,
        investor_id=None,
        file_name=file_name,
        file_path=str(file_path),
        file_hash=file_hash,
        generated_by_user_id=generated_by.id,
    )
    db.add(snapshot)
    return snapshot


def generate_investor_statement(
    db: Session,
    *,
    period: AccountingPeriod,
    investor: Investor,
    generated_by: User,
) -> ReportSnapshot:
    settings = get_settings()
    output_dir = Path(settings.reports_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    file_name = (
        f"investor-statement-{period.club_id}-{investor.id}-{period.year:04d}"
        f"{period.month:02d}-{timestamp}.pdf"
    )
    file_path = output_dir / file_name

    balance_row = db.scalar(
        select(InvestorBalance).where(
            InvestorBalance.period_id == period.id,
            InvestorBalance.club_id == period.club_id,
            InvestorBalance.investor_id == investor.id,
        )
    )
    position = db.scalar(
        select(InvestorPosition).where(
            InvestorPosition.period_id == period.id,
            InvestorPosition.investor_id == investor.id,
        )
    )
    if position is None and balance_row is None:
        raise ValueError("Investor position missing for this period.")

    pdf = canvas.Canvas(str(file_path), pagesize=A4)
    _draw_header(
        pdf,
        f"Investor Statement - {investor.name}",
        f"Period {period.year:04d}-{period.month:02d} | Club #{period.club_id}",
    )
    y = 750
    opening_balance = money(balance_row.opening_balance) if balance_row else money(position.opening_balance)
    ownership_pct = balance_row.ownership_pct if balance_row else position.ownership_pct
    contributions = money(balance_row.contributions) if balance_row else money(position.contributions)
    withdrawals = money(balance_row.withdrawals) if balance_row else money(position.withdrawals)
    net_allocation = money(balance_row.net_alloc) if balance_row else money(position.net_allocation)
    closing_balance = money(balance_row.closing_balance) if balance_row else money(position.closing_balance)

    rows = [
        ("Opening Balance", opening_balance),
        ("Ownership %", ownership_pct),
        ("Contributions", contributions),
        ("Withdrawals", withdrawals),
        ("Net Allocation", net_allocation),
        ("Closing Balance", closing_balance),
    ]
    for label, value in rows:
        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawString(50, y, label)
        pdf.setFont("Helvetica", 10)
        if isinstance(value, str):
            text = value
        else:
            text = f"{value:.6f}%" if label == "Ownership %" else f"UGX {money(value):,.2f}"
        pdf.drawString(250, y, text)
        y -= 20

    pdf.save()
    file_hash = _hash_file(file_path)
    snapshot = ReportSnapshot(
        tenant_id=period.tenant_id,
        club_id=period.club_id,
        period_id=period.id,
        investor_id=investor.id,
        report_type=ReportType.investor_statement,
        file_name=file_name,
        file_path=str(file_path),
        file_hash=file_hash,
        generated_by_user_id=generated_by.id,
    )
    db.add(snapshot)
    return snapshot
