"""Authentication and audit models."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Role(Base):
    __tablename__ = "roles"

    code: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    description: Mapped[str] = mapped_column(String(255), default="")
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    permissions: Mapped[list["RolePermission"]] = relationship(
        back_populates="role_definition", cascade="all, delete-orphan"
    )
    users: Mapped[list["User"]] = relationship(back_populates="role_definition")
    assignments: Mapped[list["UserRole"]] = relationship(
        back_populates="role_definition", cascade="all, delete-orphan"
    )


class Permission(Base):
    __tablename__ = "permissions"

    code: Mapped[str] = mapped_column(String(80), primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    module: Mapped[str] = mapped_column(String(80), index=True)
    action: Mapped[str] = mapped_column(String(40))
    sort_order: Mapped[int] = mapped_column(default=0)
    supports_scope: Mapped[bool] = mapped_column(Boolean, default=False)

    role_permissions: Mapped[list["RolePermission"]] = relationship(
        back_populates="permission_definition", cascade="all, delete-orphan"
    )


class RolePermission(Base):
    __tablename__ = "role_permissions"

    role_code: Mapped[str] = mapped_column(
        ForeignKey("roles.code", ondelete="CASCADE"), primary_key=True
    )
    permission_code: Mapped[str] = mapped_column(
        ForeignKey("permissions.code", ondelete="CASCADE"), primary_key=True
    )
    data_scope: Mapped[str] = mapped_column(String(16), default="all")

    role_definition: Mapped[Role] = relationship(back_populates="permissions")
    permission_definition: Mapped[Permission] = relationship(back_populates="role_permissions")


class UserRole(Base):
    __tablename__ = "user_roles"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role_code: Mapped[str] = mapped_column(
        ForeignKey("roles.code", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="role_assignments")
    role_definition: Mapped[Role] = relationship(back_populates="assignments")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    latest_password_ciphertext: Mapped[str | None] = mapped_column(
        String(512), nullable=True
    )
    display_name: Mapped[str] = mapped_column(
        String(80), unique=True, default="系统管理员"
    )
    role: Mapped[str] = mapped_column(
        ForeignKey("roles.code"), default="admin", index=True
    )
    team: Mapped[str] = mapped_column(String(40), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    audit_logs: Mapped[list["AuditLog"]] = relationship(back_populates="user")
    role_definition: Mapped[Role] = relationship(back_populates="users")
    role_assignments: Mapped[list[UserRole]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    assigned_roles: Mapped[list[Role]] = relationship(
        secondary="user_roles", viewonly=True, order_by="Role.name"
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_logs_created_at", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(80), index=True)
    resource: Mapped[str] = mapped_column(String(120), default="system")
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped[User | None] = relationship(back_populates="audit_logs")
