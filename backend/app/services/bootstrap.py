"""Idempotent first-run bootstrap tasks."""

from sqlalchemy import select

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.user import User, UserRole


def ensure_initial_admin() -> None:
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.username == settings.initial_admin_username))
        if user:
            return
        user = User(
            username=settings.initial_admin_username,
            display_name="系统管理员",
            role="admin",
            password_hash=hash_password(settings.initial_admin_password),
        )
        db.add(user)
        db.flush()
        db.add(UserRole(user_id=user.id, role_code="admin"))
        db.commit()
