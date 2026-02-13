from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_club_access
from app.core.security import require_roles
from app.models.enums import LedgerEntryType, PeriodStatus, RoleName
from app.models.investor import Investor
from app.models.ledger import LedgerEntry
from app.models.user import User
from app.schemas.ledger import (
    LedgerBulkImportRequest,
    LedgerEntryCreateRequest,
    LedgerEntryOut,
    LedgerEntryUpdateRequest,
)
from app.services.accounting import assert_period_writable, get_period_or_404, recalculate_period
from app.services.audit import log_audit
from app.utils.decimal_math import money


router = APIRouter(prefix="/clubs/{club_id}/periods/{period_id}/ledger", tags=["ledger"])


def _validate_ledger_payload(
    payload: LedgerEntryCreateRequest,
    investor_exists: bool,
) -> None:
    if payload.entry_type in {LedgerEntryType.contribution, LedgerEntryType.withdrawal}:
        if payload.investor_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Contribution/withdrawal entries require investor_id.",
            )
    if payload.entry_type in {LedgerEntryType.income, LedgerEntryType.expense} and payload.investor_id is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Income/expense entries must not include investor_id.",
        )
    if payload.investor_id is not None and not investor_exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Investor not found in this club.",
        )
    if payload.entry_type != LedgerEntryType.adjustment and payload.amount < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only adjustments may be negative.",
        )
    if payload.amount == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Amount cannot be zero.",
        )


def _find_investor(db: Session, club_id: int, investor_id: int | None) -> bool:
    if investor_id is None:
        return False
    return (
        db.scalar(
            select(Investor.id).where(
                Investor.id == investor_id,
                Investor.club_id == club_id,
                Investor.is_active.is_(True),
            )
        )
        is not None
    )


def _create_entry(
    db: Session,
    *,
    club_id: int,
    period_id: int,
    payload: LedgerEntryCreateRequest,
    current_user: User,
) -> LedgerEntry:
    period = get_period_or_404(db, club_id, period_id)
    assert_period_writable(period)
    investor_exists = _find_investor(db, club_id, payload.investor_id)
    _validate_ledger_payload(payload, investor_exists)
    tx_date = payload.tx_date or date.today()
    entry = LedgerEntry(
        tenant_id=period.tenant_id,
        club_id=club_id,
        period_id=period_id,
        investor_id=payload.investor_id,
        entry_type=payload.entry_type,
        amount=money(payload.amount),
        category=payload.category,
        tx_date=tx_date,
        description=payload.description,
        note=payload.note,
        reference=payload.reference,
        attachment_url=payload.attachment_url,
        created_by_user_id=current_user.id,
    )
    db.add(entry)
    db.flush()
    recalculate_period(db, period)
    log_audit(
        db,
        actor=current_user,
        tenant_id=period.tenant_id,
        action="ledger.create",
        entity_type="ledger_entry",
        entity_id=str(entry.id),
        club_id=club_id,
        period_id=period_id,
        after_state={
            "entry_type": payload.entry_type.value,
            "amount": str(entry.amount),
            "investor_id": payload.investor_id,
            "description": payload.description,
            "reference": payload.reference,
        },
    )
    return entry


@router.get("", response_model=list[LedgerEntryOut])
def list_ledger_entries(
    club_id: int,
    period_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[LedgerEntry]:
    require_club_access(db, current_user, club_id)
    get_period_or_404(db, club_id, period_id)
    return list(
        db.scalars(
            select(LedgerEntry)
            .where(and_(LedgerEntry.club_id == club_id, LedgerEntry.period_id == period_id))
            .order_by(LedgerEntry.tx_date.desc(), LedgerEntry.id.desc())
        ).all()
    )


@router.post("", response_model=LedgerEntryOut, status_code=status.HTTP_201_CREATED)
def post_ledger_entry(
    club_id: int,
    period_id: int,
    payload: LedgerEntryCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LedgerEntry:
    require_club_access(db, current_user, club_id)
    require_roles(current_user, [RoleName.admin, RoleName.fund_accountant, RoleName.advisor])
    entry = _create_entry(
        db,
        club_id=club_id,
        period_id=period_id,
        payload=payload,
        current_user=current_user,
    )
    db.commit()
    db.refresh(entry)
    return entry


@router.patch("/{entry_id}", response_model=LedgerEntryOut)
def update_ledger_entry(
    club_id: int,
    period_id: int,
    entry_id: int,
    payload: LedgerEntryUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LedgerEntry:
    require_club_access(db, current_user, club_id)
    require_roles(current_user, [RoleName.admin, RoleName.fund_accountant, RoleName.advisor])
    period = get_period_or_404(db, club_id, period_id)
    if period.status not in {PeriodStatus.draft, PeriodStatus.review}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Update is allowed only in draft/review.")

    entry = db.scalar(
        select(LedgerEntry).where(
            LedgerEntry.id == entry_id,
            LedgerEntry.club_id == club_id,
            LedgerEntry.period_id == period_id,
        )
    )
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ledger entry not found.")

    before = {
        "amount": str(entry.amount),
        "description": entry.description,
        "category": entry.category,
        "tx_date": entry.tx_date.isoformat(),
        "note": entry.note,
        "reference": entry.reference,
        "attachment_url": entry.attachment_url,
    }
    if payload.amount is not None:
        if payload.amount == 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Amount cannot be zero.")
        if entry.entry_type != LedgerEntryType.adjustment and payload.amount < 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only adjustments may be negative.")
        entry.amount = money(payload.amount)
    if payload.description is not None:
        entry.description = payload.description
    if payload.category is not None:
        entry.category = payload.category
    if payload.tx_date is not None:
        entry.tx_date = payload.tx_date
    if payload.note is not None:
        entry.note = payload.note
    if payload.reference is not None:
        entry.reference = payload.reference
    if payload.attachment_url is not None:
        entry.attachment_url = payload.attachment_url

    recalculate_period(db, period)
    log_audit(
        db,
        actor=current_user,
        tenant_id=period.tenant_id,
        action="ledger.update",
        entity_type="ledger_entry",
        entity_id=str(entry.id),
        club_id=club_id,
        period_id=period_id,
        before_state=before,
        after_state={
            "amount": str(entry.amount),
            "description": entry.description,
            "category": entry.category,
            "tx_date": entry.tx_date.isoformat(),
            "note": entry.note,
            "reference": entry.reference,
            "attachment_url": entry.attachment_url,
        },
    )
    db.commit()
    db.refresh(entry)
    return entry


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_ledger_entry(
    club_id: int,
    period_id: int,
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    require_club_access(db, current_user, club_id)
    require_roles(current_user, [RoleName.admin, RoleName.fund_accountant])
    period = get_period_or_404(db, club_id, period_id)
    if period.status != PeriodStatus.draft:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Delete is allowed only in draft.")
    entry = db.scalar(
        select(LedgerEntry).where(
            LedgerEntry.id == entry_id,
            LedgerEntry.club_id == club_id,
            LedgerEntry.period_id == period_id,
        )
    )
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ledger entry not found.")
    before = {
        "amount": str(entry.amount),
        "description": entry.description,
        "reference": entry.reference,
    }
    db.delete(entry)
    db.flush()
    recalculate_period(db, period)
    log_audit(
        db,
        actor=current_user,
        tenant_id=period.tenant_id,
        action="ledger.delete",
        entity_type="ledger_entry",
        entity_id=str(entry_id),
        club_id=club_id,
        period_id=period_id,
        before_state=before,
    )
    db.commit()
    return None


@router.post("/bulk-import")
def bulk_import_ledger(
    club_id: int,
    period_id: int,
    payload: LedgerBulkImportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    require_club_access(db, current_user, club_id)
    require_roles(current_user, [RoleName.admin, RoleName.fund_accountant, RoleName.advisor])
    period = get_period_or_404(db, club_id, period_id)
    assert_period_writable(period)

    created: list[int] = []
    for item in payload.entries:
        entry = _create_entry(
            db,
            club_id=club_id,
            period_id=period_id,
            payload=item,
            current_user=current_user,
        )
        created.append(entry.id)
    if payload.dry_run:
        db.rollback()
        return {"dry_run": True, "would_create": len(created)}
    db.commit()
    return {"dry_run": False, "created": len(created), "entry_ids": created}
