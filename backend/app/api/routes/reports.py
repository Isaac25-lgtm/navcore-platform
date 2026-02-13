from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_club_access
from app.core.security import require_roles
from app.models.club import Club
from app.models.enums import PeriodStatus, RoleName
from app.models.investor import Investor
from app.models.report import ReportSnapshot
from app.models.user import User
from app.schemas.reports import ReportGenerateResponse, ReportSnapshotOut
from app.services.accounting import get_period_or_404
from app.services.audit import log_audit
from app.services.reports import generate_investor_statement, generate_monthly_club_report


router = APIRouter(tags=["reports"])


@router.post(
    "/clubs/{club_id}/periods/{period_id}/reports/monthly-club",
    response_model=ReportGenerateResponse,
)
def create_monthly_club_report(
    club_id: int,
    period_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_club_access(db, current_user, club_id)
    require_roles(current_user, [RoleName.admin, RoleName.fund_accountant, RoleName.advisor])
    period = get_period_or_404(db, club_id, period_id)
    if period.status != PeriodStatus.closed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Reports can only be generated from closed snapshots.",
        )

    club = db.get(Club, club_id)
    snapshot = generate_monthly_club_report(
        db,
        period=period,
        club_name=club.name if club else f"Club {club_id}",
        generated_by=current_user,
    )
    db.flush()
    log_audit(
        db,
        actor=current_user,
        tenant_id=period.tenant_id,
        action="report.generate_monthly_club",
        entity_type="report",
        entity_id=str(snapshot.id),
        club_id=club_id,
        period_id=period_id,
    )
    db.commit()
    db.refresh(snapshot)
    return ReportGenerateResponse(
        report=ReportSnapshotOut(
            id=snapshot.id,
            tenant_id=snapshot.tenant_id,
            club_id=snapshot.club_id,
            period_id=snapshot.period_id,
            investor_id=snapshot.investor_id,
            report_type=snapshot.report_type,
            file_name=snapshot.file_name,
            file_hash=snapshot.file_hash,
            created_at=snapshot.created_at,
        ),
        download_url=f"/api/v1/reports/{snapshot.id}/download",
    )


@router.post(
    "/clubs/{club_id}/periods/{period_id}/reports/investor/{investor_id}",
    response_model=ReportGenerateResponse,
)
def create_investor_report(
    club_id: int,
    period_id: int,
    investor_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_club_access(db, current_user, club_id)
    require_roles(current_user, [RoleName.admin, RoleName.fund_accountant, RoleName.advisor])
    period = get_period_or_404(db, club_id, period_id)
    if period.status != PeriodStatus.closed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Reports can only be generated from closed snapshots.",
        )
    investor = db.scalar(
        select(Investor).where(
            Investor.id == investor_id,
            Investor.club_id == club_id,
            Investor.is_active.is_(True),
        )
    )
    if investor is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Investor not found.")

    snapshot = generate_investor_statement(
        db,
        period=period,
        investor=investor,
        generated_by=current_user,
    )
    db.flush()
    log_audit(
        db,
        actor=current_user,
        tenant_id=period.tenant_id,
        action="report.generate_investor_statement",
        entity_type="report",
        entity_id=str(snapshot.id),
        club_id=club_id,
        period_id=period_id,
    )
    db.commit()
    db.refresh(snapshot)
    return ReportGenerateResponse(
        report=ReportSnapshotOut(
            id=snapshot.id,
            tenant_id=snapshot.tenant_id,
            club_id=snapshot.club_id,
            period_id=snapshot.period_id,
            investor_id=snapshot.investor_id,
            report_type=snapshot.report_type,
            file_name=snapshot.file_name,
            file_hash=snapshot.file_hash,
            created_at=snapshot.created_at,
        ),
        download_url=f"/api/v1/reports/{snapshot.id}/download",
    )


@router.get("/clubs/{club_id}/periods/{period_id}/reports", response_model=list[ReportSnapshotOut])
def list_reports(
    club_id: int,
    period_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ReportSnapshotOut]:
    require_club_access(db, current_user, club_id)
    reports = list(
        db.scalars(
            select(ReportSnapshot)
            .where(
                ReportSnapshot.club_id == club_id,
                ReportSnapshot.period_id == period_id,
            )
            .order_by(ReportSnapshot.created_at.desc())
        ).all()
    )
    return [
        ReportSnapshotOut(
            id=report.id,
            tenant_id=report.tenant_id,
            club_id=report.club_id,
            period_id=report.period_id,
            investor_id=report.investor_id,
            report_type=report.report_type,
            file_name=report.file_name,
            file_hash=report.file_hash,
            created_at=report.created_at,
        )
        for report in reports
    ]


@router.get("/reports/{report_id}/download")
def download_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    snapshot = db.get(ReportSnapshot, report_id)
    if snapshot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found.")
    require_club_access(db, current_user, snapshot.club_id)
    path = Path(snapshot.file_path)
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report file missing.")
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=snapshot.file_name,
    )
