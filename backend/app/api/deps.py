from collections.abc import Generator

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.club import Club, ClubMembership
from app.models.enums import RoleName
from app.models.tenant import Role, UserRole
from app.models.user import User


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    db: Session = Depends(get_db),
    x_user_id: int | None = Header(default=None),
    x_tenant_id: int = Header(default=1),
) -> User:
    if x_user_id is None:
        # Safe default for local development.
        user = db.scalar(select(User).where(User.email == "admin@navfund.com"))
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required.",
            )
        # attach tenant-scoped roles for downstream RBAC checks
        role_rows = list(
            db.scalars(
                select(Role.name)
                .join(UserRole, UserRole.role_id == Role.id)
                .where(UserRole.user_id == user.id, UserRole.tenant_id == x_tenant_id)
            ).all()
        )
        setattr(user, "tenant_role_names", [str(role) for role in role_rows])
        setattr(user, "tenant_id_ctx", x_tenant_id)
        return user

    user = db.get(User, x_user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user.",
        )
    role_rows = list(
        db.scalars(
            select(Role.name)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user.id, UserRole.tenant_id == x_tenant_id)
        ).all()
    )
    setattr(user, "tenant_role_names", [str(role) for role in role_rows])
    setattr(user, "tenant_id_ctx", x_tenant_id)
    return user


def get_tenant_id(x_tenant_id: int = Header(default=1)) -> int:
    return x_tenant_id


def require_club_access(db: Session, user: User, club_id: int, tenant_id: int | None = None) -> None:
    scoped_tenant_id = tenant_id if tenant_id is not None else int(getattr(user, "tenant_id_ctx", 1))
    club = db.get(Club, club_id)
    if club is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Club not found.")
    if club.tenant_id != scoped_tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cross-tenant access blocked.")

    user_roles = set(str(role) for role in getattr(user, "tenant_role_names", []) if role is not None)
    if user.role == RoleName.admin or "admin" in user_roles:
        return

    membership = db.scalar(
        select(ClubMembership).where(
            ClubMembership.user_id == user.id,
            ClubMembership.club_id == club_id,
            ClubMembership.tenant_id == scoped_tenant_id,
        )
    )
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User cannot access this club.",
        )
