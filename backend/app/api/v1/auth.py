"""Session-based authentication endpoints."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_permission_scopes, get_user_role_codes
from app.core.credentials import encrypt_password
from app.core.security import hash_password, verify_password
from app.db.session import get_db
from app.models.user import Role, User
from app.schemas.auth import AuthResponse, ChangePasswordRequest, LoginRequest, UserResponse
from app.services.audit import add_audit_log

router = APIRouter(prefix="/auth", tags=["认证"])


def serialize_user(
    db: Session,
    user: User,
    *,
    must_change_password: bool | None = None,
) -> UserResponse:
    role_codes = get_user_role_codes(db, user)
    role_name_rows = db.execute(
        select(Role.code, Role.name).where(Role.code.in_(role_codes))
    ).all()
    role_name_map = {str(code): str(name) for code, name in role_name_rows}
    role_names = [role_name_map.get(code, code) for code in role_codes]
    return UserResponse(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        role=user.role,
        role_name=role_name_map.get(user.role, user.role),
        roles=role_codes,
        role_names=role_names,
        team=user.team,
        permissions=get_permission_scopes(db, user),
        must_change_password=(
            user.must_change_password
            if must_change_password is None
            else must_change_password
        ),
    )


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)) -> AuthResponse:
    login_name = payload.username.strip()
    user = db.scalar(select(User).where(User.display_name == login_name))
    if user is None:
        # Keep the original account identifier as a compatibility fallback for admin.
        user = db.scalar(select(User).where(User.username == login_name.lower()))
    if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
        add_audit_log(
            db,
            action="login_failed",
            resource="auth",
            request=request,
            detail={"login_name": login_name},
        )
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="账号或密码错误")

    first_default_password_login = (
        user.must_change_password and user.last_login_at is None
    )
    request.session.clear()
    request.session["user_id"] = user.id
    if first_default_password_login:
        request.session["defer_password_change"] = True
    user.latest_password_ciphertext = encrypt_password(payload.password)
    user.last_login_at = datetime.now(UTC).replace(tzinfo=None)
    add_audit_log(db, action="login", resource="auth", request=request, user=user)
    db.commit()
    db.refresh(user)
    return AuthResponse(
        user=serialize_user(
            db,
            user,
            must_change_password=(
                user.must_change_password and not first_default_password_login
            ),
        )
    )


@router.get("/me", response_model=AuthResponse)
def me(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AuthResponse:
    return AuthResponse(
        user=serialize_user(
            db,
            user,
            must_change_password=(
                user.must_change_password
                and not request.session.get("defer_password_change")
            ),
        )
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    add_audit_log(db, action="logout", resource="auth", request=request, user=user)
    db.commit()
    request.session.clear()


@router.post("/change-password", response_model=AuthResponse)
def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AuthResponse:
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=422, detail="当前密码不正确")
    if verify_password(payload.new_password, user.password_hash):
        raise HTTPException(status_code=422, detail="新密码不能与当前密码相同")
    user.password_hash = hash_password(payload.new_password)
    user.latest_password_ciphertext = encrypt_password(payload.new_password)
    user.must_change_password = False
    user.password_changed_at = datetime.now(UTC).replace(tzinfo=None)
    request.session.pop("defer_password_change", None)
    add_audit_log(
        db,
        action="password_change",
        resource=f"user:{user.id}",
        request=request,
        user=user,
        detail={"target_name": user.display_name},
    )
    db.commit()
    db.refresh(user)
    return AuthResponse(user=serialize_user(db, user))
