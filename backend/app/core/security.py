from collections.abc import Iterable

from fastapi import HTTPException, status

from app.models.enums import RoleName
from app.models.user import User


def require_roles(user: User, allowed_roles: Iterable[RoleName]) -> None:
    allowed = {role.value for role in set(allowed_roles)}
    legacy_map = {
        "manager": "fund_accountant",
        "analyst": "advisor",
        "viewer": "investor",
    }
    tenant_roles = set(str(role) for role in getattr(user, "tenant_role_names", []) if role is not None)
    normalized_tenant_roles = set(tenant_roles)
    normalized_tenant_roles.update(
        legacy_map[role] for role in tenant_roles if role in legacy_map
    )

    normalized_user_roles = {user.role.value}
    mapped_user_role = legacy_map.get(user.role.value)
    if mapped_user_role is not None:
        normalized_user_roles.add(mapped_user_role)

    if user.role == RoleName.admin or "admin" in normalized_tenant_roles:
        return
    if normalized_user_roles.intersection(allowed):
        return
    if normalized_tenant_roles.intersection(allowed):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Insufficient role privileges.",
    )
