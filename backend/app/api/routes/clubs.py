from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, get_tenant_id, require_club_access
from app.core.security import require_roles
from app.models.club import Club, ClubMembership
from app.models.enums import RoleName
from app.models.investor import Investor
from app.models.period import AccountingPeriod
from app.models.user import User
from app.schemas.clubs import (
    ClubCreateRequest,
    ClubMetricSummary,
    ClubSummary,
    ClubUpdateRequest,
    InvestorCreateRequest,
    InvestorSummary,
    InvestorUpdateRequest,
    MembershipCreateRequest,
    MembershipSummary,
    PeriodMetricSummary,
    PeriodCreateRequest,
    PeriodSummary,
)
from app.services.accounting import create_period_with_openings, recalculate_period
from app.services.audit import log_audit
from app.utils.decimal_math import money, pct


router = APIRouter(prefix="/clubs", tags=["clubs"])


def _list_accessible_clubs(db: Session, current_user: User, tenant_id: int) -> list[Club]:
    tenant_roles = set(str(role) for role in getattr(current_user, "tenant_role_names", []))
    if current_user.role == RoleName.admin or "admin" in tenant_roles:
        return list(
            db.scalars(select(Club).where(Club.tenant_id == tenant_id).order_by(Club.name)).all()
        )
    memberships = list(
        db.scalars(
            select(ClubMembership).where(
                ClubMembership.user_id == current_user.id,
                ClubMembership.tenant_id == tenant_id,
            )
        ).all()
    )
    club_ids = [membership.club_id for membership in memberships]
    if not club_ids:
        return []
    return list(
        db.scalars(
            select(Club)
            .where(Club.tenant_id == tenant_id, Club.id.in_(club_ids))
            .order_by(Club.name)
        ).all()
    )


def _build_period_metric(db: Session, period: AccountingPeriod) -> PeriodMetricSummary:
    totals = recalculate_period(db, period)
    opening_nav = money(period.opening_nav)
    closing_nav = money(period.closing_nav)
    return_pct = pct(
        ((closing_nav - opening_nav) / opening_nav) * Decimal("100")
        if opening_nav != 0
        else Decimal("0")
    )
    return PeriodMetricSummary(
        period_id=period.id,
        year=period.year,
        month=period.month,
        status=period.status,
        opening_nav=opening_nav,
        contributions=money(totals.contributions),
        withdrawals=money(totals.withdrawals),
        income=money(totals.income),
        expenses=money(totals.expenses),
        net_result=money(totals.net_result),
        closing_nav=closing_nav,
        mismatch=money(totals.mismatch),
        return_pct=return_pct,
    )


@router.get("", response_model=list[ClubSummary])
def list_clubs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_tenant_id),
) -> list[Club]:
    return _list_accessible_clubs(db, current_user, tenant_id)


@router.get("/metrics", response_model=list[ClubMetricSummary])
def list_club_metrics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_tenant_id),
) -> list[ClubMetricSummary]:
    clubs = _list_accessible_clubs(db, current_user, tenant_id)
    rows: list[ClubMetricSummary] = []
    updated_period = False

    for club in clubs:
        investor_count = db.scalar(
            select(func.count(Investor.id)).where(
                Investor.club_id == club.id,
                Investor.is_active.is_(True),
            )
        )
        latest_period = db.scalar(
            select(AccountingPeriod)
            .where(AccountingPeriod.club_id == club.id)
            .order_by(AccountingPeriod.year.desc(), AccountingPeriod.month.desc())
            .limit(1)
        )
        latest_metric = None
        if latest_period is not None:
            latest_metric = _build_period_metric(db, latest_period)
            updated_period = True

        rows.append(
            ClubMetricSummary(
                id=club.id,
                code=club.code,
                name=club.name,
                currency=club.currency,
                is_active=club.is_active,
                investor_count=int(investor_count or 0),
                latest_period=latest_metric,
            )
        )

    if updated_period:
        db.commit()
    return rows


@router.get("/{club_id}", response_model=ClubSummary)
def get_club(
    club_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_tenant_id),
) -> Club:
    require_club_access(db, current_user, club_id, tenant_id=tenant_id)
    club = db.get(Club, club_id)
    if club is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Club not found.")
    return club


@router.post("", response_model=ClubSummary, status_code=status.HTTP_201_CREATED)
def create_club(
    payload: ClubCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_tenant_id),
) -> Club:
    require_roles(current_user, [RoleName.admin, RoleName.fund_accountant])
    exists = db.scalar(select(Club).where(Club.tenant_id == tenant_id, Club.code == payload.code.upper()))
    if exists:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Club code already exists.")
    club = Club(
        tenant_id=tenant_id,
        code=payload.code.upper(),
        name=payload.name,
        currency=payload.currency.upper(),
    )
    db.add(club)
    db.flush()
    log_audit(
        db,
        actor=current_user,
        tenant_id=tenant_id,
        action="club.create",
        entity_type="club",
        entity_id=str(club.id),
        club_id=club.id,
        after_state={"code": club.code, "name": club.name},
    )
    db.commit()
    db.refresh(club)
    return club


@router.patch("/{club_id}", response_model=ClubSummary)
def update_club(
    club_id: int,
    payload: ClubUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_tenant_id),
) -> Club:
    require_club_access(db, current_user, club_id, tenant_id=tenant_id)
    require_roles(current_user, [RoleName.admin, RoleName.fund_accountant])
    club = db.get(Club, club_id)
    if club is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Club not found.")
    before = {"name": club.name, "currency": club.currency, "is_active": club.is_active}
    if payload.name is not None:
        club.name = payload.name
    if payload.currency is not None:
        club.currency = payload.currency.upper()
    if payload.is_active is not None:
        club.is_active = payload.is_active
    log_audit(
        db,
        actor=current_user,
        tenant_id=tenant_id,
        action="club.update",
        entity_type="club",
        entity_id=str(club.id),
        club_id=club.id,
        before_state=before,
        after_state={"name": club.name, "currency": club.currency, "is_active": club.is_active},
    )
    db.commit()
    db.refresh(club)
    return club


@router.delete("/{club_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_club(
    club_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_tenant_id),
) -> None:
    require_club_access(db, current_user, club_id, tenant_id=tenant_id)
    require_roles(current_user, [RoleName.admin])
    club = db.get(Club, club_id)
    if club is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Club not found.")
    db.delete(club)
    log_audit(
        db,
        actor=current_user,
        tenant_id=tenant_id,
        action="club.delete",
        entity_type="club",
        entity_id=str(club_id),
        club_id=club_id,
    )
    db.commit()
    return None


@router.get("/{club_id}/investors", response_model=list[InvestorSummary])
def list_investors(
    club_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_tenant_id),
) -> list[Investor]:
    require_club_access(db, current_user, club_id, tenant_id=tenant_id)
    return list(
        db.scalars(
            select(Investor)
            .where(and_(Investor.club_id == club_id, Investor.is_active.is_(True)))
            .order_by(Investor.name)
        ).all()
    )


@router.post("/{club_id}/investors", response_model=InvestorSummary, status_code=status.HTTP_201_CREATED)
def create_investor(
    club_id: int,
    payload: InvestorCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_tenant_id),
) -> Investor:
    require_club_access(db, current_user, club_id, tenant_id=tenant_id)
    require_roles(current_user, [RoleName.admin, RoleName.fund_accountant, RoleName.advisor])
    investor = db.scalar(
        select(Investor).where(
            Investor.club_id == club_id,
            Investor.investor_code == payload.investor_code,
        )
    )
    if investor is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Investor code already exists in this club.",
        )
    investor = Investor(
        tenant_id=tenant_id,
        club_id=club_id,
        investor_code=payload.investor_code.upper(),
        name=payload.name,
        is_active=True,
    )
    db.add(investor)
    db.flush()
    db.add(ClubMembership(tenant_id=tenant_id, club_id=club_id, investor_id=investor.id))
    log_audit(
        db,
        actor=current_user,
        tenant_id=tenant_id,
        action="investor.create",
        entity_type="investor",
        entity_id=str(investor.id),
        club_id=club_id,
        after_state={"name": investor.name, "code": investor.investor_code},
    )
    db.commit()
    db.refresh(investor)
    return investor


@router.get("/{club_id}/investors/{investor_id}", response_model=InvestorSummary)
def get_investor(
    club_id: int,
    investor_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_tenant_id),
) -> Investor:
    require_club_access(db, current_user, club_id, tenant_id=tenant_id)
    investor = db.scalar(
        select(Investor).where(Investor.id == investor_id, Investor.club_id == club_id)
    )
    if investor is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Investor not found.")
    return investor


@router.patch("/{club_id}/investors/{investor_id}", response_model=InvestorSummary)
def update_investor(
    club_id: int,
    investor_id: int,
    payload: InvestorUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_tenant_id),
) -> Investor:
    require_club_access(db, current_user, club_id, tenant_id=tenant_id)
    require_roles(current_user, [RoleName.admin, RoleName.fund_accountant, RoleName.advisor])
    investor = db.scalar(
        select(Investor).where(Investor.id == investor_id, Investor.club_id == club_id)
    )
    if investor is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Investor not found.")
    before = {"name": investor.name, "is_active": investor.is_active}
    if payload.name is not None:
        investor.name = payload.name
    if payload.is_active is not None:
        investor.is_active = payload.is_active
    log_audit(
        db,
        actor=current_user,
        tenant_id=tenant_id,
        action="investor.update",
        entity_type="investor",
        entity_id=str(investor.id),
        club_id=club_id,
        before_state=before,
        after_state={"name": investor.name, "is_active": investor.is_active},
    )
    db.commit()
    db.refresh(investor)
    return investor


@router.delete("/{club_id}/investors/{investor_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_investor(
    club_id: int,
    investor_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_tenant_id),
) -> None:
    require_club_access(db, current_user, club_id, tenant_id=tenant_id)
    require_roles(current_user, [RoleName.admin, RoleName.fund_accountant])
    investor = db.scalar(
        select(Investor).where(Investor.id == investor_id, Investor.club_id == club_id)
    )
    if investor is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Investor not found.")
    investor.is_active = False
    log_audit(
        db,
        actor=current_user,
        tenant_id=tenant_id,
        action="investor.delete",
        entity_type="investor",
        entity_id=str(investor_id),
        club_id=club_id,
    )
    db.commit()
    return None


@router.get("/{club_id}/memberships", response_model=list[MembershipSummary])
def list_memberships(
    club_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_tenant_id),
) -> list[ClubMembership]:
    require_club_access(db, current_user, club_id, tenant_id=tenant_id)
    return list(
        db.scalars(
            select(ClubMembership)
            .where(ClubMembership.club_id == club_id, ClubMembership.investor_id.is_not(None))
            .order_by(ClubMembership.id.desc())
        ).all()
    )


@router.post("/{club_id}/memberships", response_model=MembershipSummary, status_code=status.HTTP_201_CREATED)
def create_membership(
    club_id: int,
    payload: MembershipCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_tenant_id),
) -> ClubMembership:
    require_club_access(db, current_user, club_id, tenant_id=tenant_id)
    require_roles(current_user, [RoleName.admin, RoleName.fund_accountant, RoleName.advisor])
    investor = db.scalar(
        select(Investor).where(
            Investor.id == payload.investor_id,
            Investor.tenant_id == tenant_id,
            Investor.is_active.is_(True),
        )
    )
    if investor is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Investor not found.")
    exists = db.scalar(
        select(ClubMembership).where(
            ClubMembership.club_id == club_id,
            ClubMembership.investor_id == payload.investor_id,
        )
    )
    if exists:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Membership already exists.")
    membership = ClubMembership(
        tenant_id=tenant_id,
        club_id=club_id,
        investor_id=payload.investor_id,
    )
    db.add(membership)
    db.flush()
    log_audit(
        db,
        actor=current_user,
        tenant_id=tenant_id,
        action="membership.create",
        entity_type="club_membership",
        entity_id=str(membership.id),
        club_id=club_id,
        after_state={"investor_id": payload.investor_id},
    )
    db.commit()
    db.refresh(membership)
    return membership


@router.delete("/{club_id}/memberships/{membership_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_membership(
    club_id: int,
    membership_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_tenant_id),
) -> None:
    require_club_access(db, current_user, club_id, tenant_id=tenant_id)
    require_roles(current_user, [RoleName.admin, RoleName.fund_accountant])
    membership = db.scalar(
        select(ClubMembership).where(
            ClubMembership.id == membership_id,
            ClubMembership.club_id == club_id,
            ClubMembership.investor_id.is_not(None),
        )
    )
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Membership not found.")
    db.delete(membership)
    log_audit(
        db,
        actor=current_user,
        tenant_id=tenant_id,
        action="membership.delete",
        entity_type="club_membership",
        entity_id=str(membership_id),
        club_id=club_id,
    )
    db.commit()
    return None


@router.get("/{club_id}/periods", response_model=list[PeriodSummary])
def list_periods(
    club_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_tenant_id),
) -> list[AccountingPeriod]:
    require_club_access(db, current_user, club_id, tenant_id=tenant_id)
    return list(
        db.scalars(
            select(AccountingPeriod)
            .where(AccountingPeriod.club_id == club_id)
            .order_by(AccountingPeriod.year.desc(), AccountingPeriod.month.desc())
        ).all()
    )


@router.get("/{club_id}/period-metrics", response_model=list[PeriodMetricSummary])
def list_period_metrics(
    club_id: int,
    limit: int = 12,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_tenant_id),
) -> list[PeriodMetricSummary]:
    require_club_access(db, current_user, club_id, tenant_id=tenant_id)
    safe_limit = max(1, min(limit, 60))
    periods = list(
        db.scalars(
            select(AccountingPeriod)
            .where(AccountingPeriod.club_id == club_id)
            .order_by(AccountingPeriod.year.desc(), AccountingPeriod.month.desc())
            .limit(safe_limit)
        ).all()
    )
    rows = [_build_period_metric(db, period) for period in periods]
    if periods:
        db.commit()
    return rows


@router.post("/{club_id}/periods", response_model=PeriodSummary, status_code=status.HTTP_201_CREATED)
def create_period(
    club_id: int,
    payload: PeriodCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_tenant_id),
):
    require_club_access(db, current_user, club_id, tenant_id=tenant_id)
    require_roles(current_user, [RoleName.admin, RoleName.fund_accountant, RoleName.advisor])

    opening_map = None
    if payload.investor_openings:
        opening_map = {item.investor_id: money(item.opening_balance) for item in payload.investor_openings}

    period = create_period_with_openings(
        db,
        club_id=club_id,
        year=payload.year,
        month=payload.month,
        opening_nav=money(payload.opening_nav) if payload.opening_nav is not None else None,
        investor_openings=opening_map,
    )
    log_audit(
        db,
        actor=current_user,
        tenant_id=tenant_id,
        action="period.create",
        entity_type="period",
        entity_id=str(period.id),
        club_id=club_id,
        period_id=period.id,
        after_state={
            "year": period.year,
            "month": period.month,
            "year_month": period.year_month,
            "opening_nav": str(period.opening_nav),
            "status": period.status.value,
        },
    )
    db.commit()
    db.refresh(period)
    return period
