"""Shared API dependencies."""

from collections.abc import Callable

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import PERMISSION_DEFINITIONS
from app.db.session import get_db
from app.models.user import Permission, RolePermission, User, UserRole

SCOPE_RANK = {"self": 0, "team": 1, "all": 2}


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="请先登录")
    user = db.get(User, int(user_id))
    if not user or not user.is_active:
        request.session.clear()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录状态已失效")
    return user


def get_user_role_codes(db: Session, user: User) -> list[str]:
    cached = user.__dict__.get("_effective_role_codes")
    if isinstance(cached, list):
        return cached
    assigned = list(
        db.scalars(
            select(UserRole.role_code)
            .where(UserRole.user_id == user.id)
            .order_by(UserRole.created_at, UserRole.role_code)
        )
    )
    codes = [user.role]
    codes.extend(code for code in assigned if code != user.role)
    effective = list(dict.fromkeys(codes))
    user.__dict__["_effective_role_codes"] = effective
    return effective


def user_has_role(db: Session, user: User, role_code: str) -> bool:
    return role_code in get_user_role_codes(db, user)


def require_system_admin(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> User:
    if not user_has_role(db, user, "admin"):
        raise HTTPException(status_code=403, detail="仅系统管理员可访问系统管理")
    return user


def get_permission_scopes(db: Session, user: User) -> dict[str, str]:
    """Return the effective permission -> data-scope mapping for a user."""
    cached = user.__dict__.get("_effective_permission_scopes")
    if isinstance(cached, dict):
        return cached
    role_codes = get_user_role_codes(db, user)
    if "admin" in role_codes:
        scopes = {item["code"]: "all" for item in PERMISSION_DEFINITIONS}
        user.__dict__["_effective_permission_scopes"] = scopes
        return scopes
    rows = db.execute(
        select(RolePermission.permission_code, RolePermission.data_scope)
        .join(Permission, Permission.code == RolePermission.permission_code)
        .where(RolePermission.role_code.in_(role_codes))
        .order_by(Permission.sort_order)
    ).all()
    scopes: dict[str, str] = {}
    for code, scope in rows:
        permission_code = str(code)
        data_scope = str(scope)
        current = scopes.get(permission_code)
        if current is None or SCOPE_RANK[data_scope] > SCOPE_RANK[current]:
            scopes[permission_code] = data_scope
    user.__dict__["_effective_permission_scopes"] = scopes
    return scopes


def get_permission_scope(db: Session, user: User, permission_code: str) -> str | None:
    return get_permission_scopes(db, user).get(permission_code)


def require_permission(permission_code: str) -> Callable[..., User]:
    def dependency(
        db: Session = Depends(get_db),
        user: User = Depends(get_current_user),
    ) -> User:
        if get_permission_scope(db, user, permission_code) is None:
            raise HTTPException(status_code=403, detail="当前账号无此操作权限")
        return user

    return dependency


def require_any_permission(*permission_codes: str) -> Callable[..., User]:
    def dependency(
        db: Session = Depends(get_db),
        user: User = Depends(get_current_user),
    ) -> User:
        if not any(get_permission_scope(db, user, code) for code in permission_codes):
            raise HTTPException(status_code=403, detail="当前账号无此操作权限")
        return user

    return dependency
