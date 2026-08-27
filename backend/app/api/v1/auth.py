"""Session-based authentication endpoints."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.security import verify_password
from app.db.session import get_db
from app.models.user import AuditLog, User
from app.schemas.auth import AuthResponse, LoginRequest, UserResponse

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)) -> AuthResponse:
    user = db.scalar(select(User).where(User.username == payload.username))
    if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="账号或密码错误")

    request.session.clear()
    request.session["user_id"] = user.id
    user.last_login_at = datetime.now(UTC).replace(tzinfo=None)
    db.add(
        AuditLog(
            user_id=user.id,
            action="login",
            resource="auth",
            ip_address=request.client.host if request.client else None,
        )
    )
    db.commit()
    db.refresh(user)
    return AuthResponse(user=UserResponse.model_validate(user))


@router.get("/me", response_model=AuthResponse)
def me(user: User = Depends(get_current_user)) -> AuthResponse:
    return AuthResponse(user=UserResponse.model_validate(user))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request) -> None:
    request.session.clear()
