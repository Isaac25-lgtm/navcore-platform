import csv
import io
from datetime import datetime

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_club_access
from app.models.nav import InvestorBalance
from app.models.user import User
from app.services.nav_engine import compute_monthly_nav


router = APIRouter(tags=["exports"])


def _build_rows(db: Session, club_id: int, period_id: int) -> list[dict]:
    snapshot_rows = list(
        db.scalars(
            select(InvestorBalance)
            .where(InvestorBalance.club_id == club_id, InvestorBalance.period_id == period_id)
            .order_by(InvestorBalance.investor_id)
        ).all()
    )
    if snapshot_rows:
        return [
            {
                "investor_id": row.investor_id,
                "opening_balance": row.opening_balance,
                "ownership_pct": row.ownership_pct,
                "income_alloc": row.income_alloc,
                "expense_alloc": row.expense_alloc,
                "net_alloc": row.net_alloc,
                "contributions": row.contributions,
                "withdrawals": row.withdrawals,
                "closing_balance": row.closing_balance,
            }
            for row in snapshot_rows
        ]

    preview = compute_monthly_nav(club_id, period_id, db=db)
    return [
        {
            "investor_id": row.investor_id,
            "opening_balance": row.opening_balance,
            "ownership_pct": row.ownership_pct,
            "income_alloc": row.income_share,
            "expense_alloc": row.expense_share,
            "net_alloc": row.net_alloc,
            "contributions": row.contributions,
            "withdrawals": row.withdrawals,
            "closing_balance": row.closing_balance,
        }
        for row in preview.allocations
    ]


@router.get("/clubs/{club_id}/periods/{period_id}/exports/csv")
def export_csv(
    club_id: int,
    period_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_club_access(db, current_user, club_id)
    rows = _build_rows(db, club_id, period_id)
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "investor_id",
            "opening_balance",
            "ownership_pct",
            "income_alloc",
            "expense_alloc",
            "net_alloc",
            "contributions",
            "withdrawals",
            "closing_balance",
        ],
    )
    writer.writeheader()
    writer.writerows(rows)
    output.seek(0)
    filename = f"investor-balances-{club_id}-{period_id}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/clubs/{club_id}/periods/{period_id}/exports/excel")
def export_excel(
    club_id: int,
    period_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_club_access(db, current_user, club_id)
    rows = _build_rows(db, club_id, period_id)
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "InvestorBalances"
    headers = [
        "investor_id",
        "opening_balance",
        "ownership_pct",
        "income_alloc",
        "expense_alloc",
        "net_alloc",
        "contributions",
        "withdrawals",
        "closing_balance",
    ]
    sheet.append(headers)
    for row in rows:
        sheet.append([row[key] for key in headers])

    stream = io.BytesIO()
    workbook.save(stream)
    stream.seek(0)
    filename = f"investor-balances-{club_id}-{period_id}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.xlsx"
    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
