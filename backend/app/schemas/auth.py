"""Authentication schemas."""

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    display_name: str
    role: str
    role_name: str
    roles: list[str]
    role_names: list[str]
    team: str
    permissions: dict[str, str]
    must_change_password: bool


class AuthResponse(BaseModel):
    user: UserResponse


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=6, max_length=128)
