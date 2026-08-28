"""Validation schemas for account and role management."""

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.permissions import PERMISSION_CODES, SCOPES


class UserCreate(BaseModel):
    username: str = Field(
        default="",
        max_length=64,
        pattern=r"^$|^[A-Za-z0-9._-]{2,64}$",
    )
    display_name: str = Field(min_length=1, max_length=80)
    team: str = Field(default="", max_length=40)
    roles: list[str] = Field(default_factory=list, min_length=1, max_length=12)
    role: str = Field(default="", max_length=32)

    @field_validator("username", "display_name", "team", "role", mode="before")
    @classmethod
    def strip_text(cls, value: object) -> str:
        return str(value or "").strip()

    @field_validator("roles", mode="before")
    @classmethod
    def normalize_roles(cls, value: object) -> list[str]:
        return [str(item).strip() for item in list(value or []) if str(item).strip()]

    @model_validator(mode="after")
    def support_legacy_role(self) -> "UserCreate":
        if not self.roles and self.role:
            self.roles = [self.role]
        if not self.roles:
            raise ValueError("至少选择一个岗位角色")
        self.roles = list(dict.fromkeys(self.roles))
        return self


class UserUpdate(BaseModel):
    display_name: str = Field(min_length=1, max_length=80)
    team: str = Field(default="", max_length=40)
    roles: list[str] = Field(default_factory=list, min_length=1, max_length=12)
    role: str = Field(default="", max_length=32)
    is_active: bool

    @field_validator("display_name", "team", "role", mode="before")
    @classmethod
    def strip_text(cls, value: object) -> str:
        return str(value or "").strip()

    @field_validator("roles", mode="before")
    @classmethod
    def normalize_roles(cls, value: object) -> list[str]:
        return [str(item).strip() for item in list(value or []) if str(item).strip()]

    @model_validator(mode="after")
    def support_legacy_role(self) -> "UserUpdate":
        if not self.roles and self.role:
            self.roles = [self.role]
        if not self.roles:
            raise ValueError("至少选择一个岗位角色")
        self.roles = list(dict.fromkeys(self.roles))
        return self


class RoleInput(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    description: str = Field(default="", max_length=255)
    permissions: dict[str, str] = Field(default_factory=dict)

    @field_validator("name", "description", mode="before")
    @classmethod
    def strip_text(cls, value: object) -> str:
        return str(value or "").strip()

    @field_validator("permissions")
    @classmethod
    def validate_permissions(cls, value: dict[str, str]) -> dict[str, str]:
        unknown = set(value) - PERMISSION_CODES
        if unknown:
            raise ValueError(f"包含未知权限：{', '.join(sorted(unknown))}")
        invalid_scopes = set(value.values()) - SCOPES
        if invalid_scopes:
            raise ValueError("权限数据范围只能是 self、team 或 all")
        return value
