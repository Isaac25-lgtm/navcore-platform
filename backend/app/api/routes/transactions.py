from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.api.routes.ledger import (
    bulk_import_ledger,
    delete_ledger_entry,
    list_ledger_entries,
    post_ledger_entry,
    update_ledger_entry,
)
from app.models.user import User
from app.schemas.ledger import LedgerBulkImportRequest, LedgerEntryCreateRequest, LedgerEntryOut, LedgerEntryUpdateRequest


router = APIRouter(prefix="/clubs/{club_id}/periods/{period_id}/transactions", tags=["transactions"])


@router.get("", response_model=list[LedgerEntryOut])
def list_transactions(
    club_id: int,
    period_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return list_ledger_entries(club_id=club_id, period_id=period_id, db=db, current_user=current_user)


@router.post("", response_model=LedgerEntryOut)
def create_transaction(
    club_id: int,
    period_id: int,
    payload: LedgerEntryCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return post_ledger_entry(
        club_id=club_id,
        period_id=period_id,
        payload=payload,
        db=db,
        current_user=current_user,
    )


@router.patch("/{entry_id}", response_model=LedgerEntryOut)
def update_transaction(
    club_id: int,
    period_id: int,
    entry_id: int,
    payload: LedgerEntryUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return update_ledger_entry(
        club_id=club_id,
        period_id=period_id,
        entry_id=entry_id,
        payload=payload,
        db=db,
        current_user=current_user,
    )


@router.delete("/{entry_id}", status_code=204)
def delete_transaction(
    club_id: int,
    period_id: int,
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return delete_ledger_entry(
        club_id=club_id,
        period_id=period_id,
        entry_id=entry_id,
        db=db,
        current_user=current_user,
    )


@router.post("/import")
def import_transactions(
    club_id: int,
    period_id: int,
    payload: LedgerBulkImportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return bulk_import_ledger(
        club_id=club_id,
        period_id=period_id,
        payload=payload,
        db=db,
        current_user=current_user,
    )
