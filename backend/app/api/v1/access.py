"""Account, role, permission, and audit-log management APIs."""

from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_user_role_codes, require_permission, require_system_admin
from app.core.credentials import decrypt_password, encrypt_password
from app.core.permissions import PERMISSION_DEFINITIONS
from app.core.security import hash_password, verify_password
from app.db.session import get_db
from app.models.user import AuditLog, Permission, Role, RolePermission, User, UserRole
from app.schemas.access import RoleInput, UserCreate, UserUpdate
from app.services.audit import add_audit_log

router = APIRouter(
    prefix="/access",
    tags=["账号与权限"],
    dependencies=[Depends(require_system_admin)],
)
DEFAULT_PASSWORD = "423766"


def generated_employee_number(db: Session, user_id: int) -> str:
    """Generate a stable login number from the database id, skipping old collisions."""
    sequence = user_id
    while True:
        candidate = f"YB{sequence:04d}"
        if db.scalar(select(User.id).where(User.username == candidate)) is None:
            return candidate
        sequence += 1


def serialize_user(user: User) -> dict[str, object]:
    role_name_map = {role.code: role.name for role in user.assigned_roles}
    role_codes = [user.role]
    role_codes.extend(
        role.code
        for role in user.assigned_roles
        if role.code != user.role
    )
    role_codes = list(dict.fromkeys(role_codes))
    role_names = [role_name_map.get(code, code) for code in role_codes]
    latest_password = decrypt_password(user.latest_password_ciphertext)
    if (
        latest_password is None
        and user.must_change_password
        and verify_password(DEFAULT_PASSWORD, user.password_hash)
    ):
        latest_password = DEFAULT_PASSWORD
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role,
        "role_name": role_name_map.get(user.role, user.role),
        "roles": role_codes,
        "role_names": role_names,
        "team": user.team,
        "is_active": user.is_active,
        "must_change_password": user.must_change_password,
        "latest_password": latest_password,
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


def serialize_role(db: Session, role: Role) -> dict[str, object]:
    return {
        "code": role.code,
        "name": role.name,
        "description": role.description,
        "is_system": role.is_system,
        "user_count": db.scalar(
            select(func.count(func.distinct(UserRole.user_id))).where(
                UserRole.role_code == role.code
            )
        )
        or 0,
        "permissions": {
            grant.permission_code: grant.data_scope for grant in role.permissions
        },
    }


def get_role(db: Session, role_code: str) -> Role:
    role = db.scalar(
        select(Role)
        .options(selectinload(Role.permissions))
        .where(Role.code == role_code)
    )
    if role is None:
        raise HTTPException(status_code=404, detail="角色不存在")
    return role


def normalized_grants(db: Session, values: dict[str, str]) -> dict[str, str]:
    definitions = {
        item.code: item for item in db.scalars(select(Permission)).all()
    }
    missing = set(values) - set(definitions)
    if missing:
        raise HTTPException(status_code=422, detail="权限目录已变化，请刷新页面后重试")
    return {
        code: scope if definitions[code].supports_scope else "all"
        for code, scope in values.items()
    }


def replace_role_permissions(db: Session, role: Role, values: dict[str, str]) -> None:
    grants = normalized_grants(db, values)
    db.execute(delete(RolePermission).where(RolePermission.role_code == role.code))
    db.flush()
    for permission_code, data_scope in grants.items():
        db.add(
            RolePermission(
                role_code=role.code,
                permission_code=permission_code,
                data_scope=data_scope,
            )
        )


def validate_role_codes(db: Session, values: list[str]) -> list[str]:
    role_codes = list(dict.fromkeys(values))
    existing = set(
        db.scalars(select(Role.code).where(Role.code.in_(role_codes))).all()
    )
    if len(existing) != len(role_codes):
        raise HTTPException(status_code=422, detail="所选角色不存在，请刷新后重试")
    return role_codes


def replace_user_roles(db: Session, user: User, role_codes: list[str]) -> None:
    user.role = role_codes[0]
    db.execute(delete(UserRole).where(UserRole.user_id == user.id))
    db.flush()
    for role_code in role_codes:
        db.add(UserRole(user_id=user.id, role_code=role_code))
    user.__dict__.pop("_effective_role_codes", None)
    user.__dict__.pop("_effective_permission_scopes", None)


@router.get("/overview")
def access_overview(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("accounts.view")),
) -> dict[str, object]:
    total = db.scalar(select(func.count(User.id))) or 0
    active = db.scalar(select(func.count(User.id)).where(User.is_active.is_(True))) or 0
    administrators = (
        db.scalar(
            select(func.count(func.distinct(UserRole.user_id)))
            .join(User, User.id == UserRole.user_id)
            .where(UserRole.role_code == "admin", User.is_active.is_(True))
        )
        or 0
    )
    teams = sorted(
        {
            str(value).strip()
            for value in db.scalars(select(User.team).distinct()).all()
            if str(value or "").strip()
        }
        | {"发货组", "退货组"}
    )
    return {
        "summary": {
            "total": total,
            "active": active,
            "disabled": total - active,
            "administrators": administrators,
        },
        "teams": teams,
    }


@router.get("/users")
def list_users(
    keyword: str = "",
    role: str = "",
    team: str = "",
    active: bool | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("accounts.view")),
) -> list[dict[str, object]]:
    statement = select(User).options(selectinload(User.assigned_roles))
    if keyword.strip():
        term = f"%{keyword.strip()}%"
        statement = statement.where(
            or_(User.username.like(term), User.display_name.like(term))
        )
    if role:
        statement = statement.where(
            User.role_assignments.any(UserRole.role_code == role)
        )
    if team:
        statement = statement.where(User.team == team)
    if active is not None:
        statement = statement.where(User.is_active.is_(active))
    users = db.scalars(
        statement.order_by(User.is_active.desc(), User.display_name)
    ).all()
    return [serialize_user(user) for user in users]


@router.post("/users", status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    request: Request,
    db: Session = Depends(get_db),
    operator: User = Depends(require_permission("accounts.manage")),
) -> dict[str, object]:
    requested_username = payload.username.lower()
    if requested_username and db.scalar(
        select(User.id).where(User.username == requested_username)
    ) is not None:
        raise HTTPException(status_code=409, detail="用户名已存在")
    if db.scalar(
        select(User.id).where(User.display_name == payload.display_name)
    ) is not None:
        raise HTTPException(status_code=409, detail="姓名已存在，请填写可区分的姓名")
    role_codes = validate_role_codes(db, payload.roles)
    password = DEFAULT_PASSWORD
    target = User(
        username=requested_username or f"pending_{uuid4().hex}",
        display_name=payload.display_name,
        team=payload.team,
        role=role_codes[0],
        is_active=True,
        must_change_password=True,
        password_hash=hash_password(password),
        latest_password_ciphertext=encrypt_password(password),
    )
    db.add(target)
    db.flush()
    if not requested_username:
        target.username = generated_employee_number(db, target.id)
    replace_user_roles(db, target, role_codes)
    add_audit_log(
        db,
        action="user_create",
        resource=f"user:{target.id}",
        request=request,
        user=operator,
        detail={
            "target_name": target.display_name,
            "username": target.username,
            "roles": role_codes,
            "team": target.team,
        },
    )
    db.commit()
    target = db.scalar(
        select(User)
        .options(selectinload(User.assigned_roles))
        .where(User.id == target.id)
    )
    return {"user": serialize_user(target), "temporary_password": password}


@router.put("/users/{user_id}")
def update_user(
    user_id: int,
    payload: UserUpdate,
    request: Request,
    db: Session = Depends(get_db),
    operator: User = Depends(require_permission("accounts.manage")),
) -> dict[str, object]:
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="账号不存在")
    if db.scalar(
        select(User.id).where(
            User.display_name == payload.display_name,
            User.id != target.id,
        )
    ) is not None:
        raise HTTPException(status_code=409, detail="姓名已存在，请填写可区分的姓名")
    role_codes = validate_role_codes(db, payload.roles)
    current_roles = get_user_role_codes(db, target)
    if target.id == operator.id and (
        set(role_codes) != set(current_roles) or payload.is_active != target.is_active
    ):
        raise HTTPException(status_code=409, detail="不能修改自己的岗位角色或账号状态")
    removes_active_admin = (
        "admin" in current_roles
        and target.is_active
        and ("admin" not in role_codes or not payload.is_active)
    )
    if removes_active_admin:
        active_admins = (
            db.scalar(
                select(func.count(func.distinct(UserRole.user_id)))
                .join(User, User.id == UserRole.user_id)
                .where(UserRole.role_code == "admin", User.is_active.is_(True))
            )
            or 0
        )
        if active_admins <= 1:
            raise HTTPException(status_code=409, detail="必须至少保留一个有效管理员")
    before = {
        "display_name": target.display_name,
        "team": target.team,
        "roles": current_roles,
        "is_active": target.is_active,
    }
    target.display_name = payload.display_name
    target.team = payload.team
    target.is_active = payload.is_active
    replace_user_roles(db, target, role_codes)
    add_audit_log(
        db,
        action="user_update",
        resource=f"user:{target.id}",
        request=request,
        user=operator,
        detail={
            "target_name": target.display_name,
            "before": before,
            "after": {
                "display_name": target.display_name,
                "team": target.team,
                "roles": role_codes,
                "is_active": target.is_active,
            },
        },
    )
    db.commit()
    target = db.scalar(
        select(User)
        .options(selectinload(User.assigned_roles))
        .where(User.id == target.id)
    )
    return serialize_user(target)


@router.post("/users/{user_id}/reset-password")
def reset_password(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    operator: User = Depends(require_permission("accounts.manage")),
) -> dict[str, str]:
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="账号不存在")
    if target.id == operator.id:
        raise HTTPException(status_code=409, detail="请通过右上角账号入口修改自己的密码")
    password = DEFAULT_PASSWORD
    target.password_hash = hash_password(password)
    target.latest_password_ciphertext = encrypt_password(password)
    target.must_change_password = True
    target.password_changed_at = None
    target.last_login_at = None
    add_audit_log(
        db,
        action="password_reset",
        resource=f"user:{target.id}",
        request=request,
        user=operator,
        detail={"target_name": target.display_name, "username": target.username},
    )
    db.commit()
    return {"temporary_password": password}


@router.get("/permissions")
def list_permissions(
    _: User = Depends(require_permission("roles.view")),
) -> list[dict[str, object]]:
    return [dict(item) for item in PERMISSION_DEFINITIONS]


@router.get("/roles")
def list_roles(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("roles.view")),
) -> list[dict[str, object]]:
    roles = db.scalars(
        select(Role)
        .options(selectinload(Role.permissions))
        .order_by(Role.is_system.desc(), Role.name)
    ).all()
    return [serialize_role(db, role) for role in roles]


@router.post("/roles", status_code=status.HTTP_201_CREATED)
def create_role(
    payload: RoleInput,
    request: Request,
    db: Session = Depends(get_db),
    operator: User = Depends(require_permission("roles.manage")),
) -> dict[str, object]:
    if db.scalar(select(Role.code).where(Role.name == payload.name)) is not None:
        raise HTTPException(status_code=409, detail="角色名称已存在")
    target = Role(
        code=f"custom_{uuid4().hex[:12]}",
        name=payload.name,
        description=payload.description,
        is_system=False,
    )
    db.add(target)
    db.flush()
    replace_role_permissions(db, target, payload.permissions)
    add_audit_log(
        db,
        action="role_create",
        resource=f"role:{target.code}",
        request=request,
        user=operator,
        detail={"target_name": target.name, "permissions": payload.permissions},
    )
    db.commit()
    return serialize_role(db, get_role(db, target.code))


@router.put("/roles/{role_code}")
def update_role(
    role_code: str,
    payload: RoleInput,
    request: Request,
    db: Session = Depends(get_db),
    operator: User = Depends(require_permission("roles.manage")),
) -> dict[str, object]:
    target = get_role(db, role_code)
    if target.code == "admin":
        raise HTTPException(status_code=409, detail="系统管理员权限固定为全量，不能修改")
    duplicate = db.scalar(
        select(Role.code).where(Role.name == payload.name, Role.code != target.code)
    )
    if duplicate is not None:
        raise HTTPException(status_code=409, detail="角色名称已存在")
    before_permissions = {
        item.permission_code: item.data_scope for item in target.permissions
    }
    target.name = payload.name
    target.description = payload.description
    replace_role_permissions(db, target, payload.permissions)
    add_audit_log(
        db,
        action="role_update",
        resource=f"role:{target.code}",
        request=request,
        user=operator,
        detail={
            "target_name": target.name,
            "before_permissions": before_permissions,
            "after_permissions": payload.permissions,
        },
    )
    db.commit()
    return serialize_role(db, get_role(db, target.code))


@router.delete("/roles/{role_code}", status_code=status.HTTP_204_NO_CONTENT)
def delete_role(
    role_code: str,
    request: Request,
    db: Session = Depends(get_db),
    operator: User = Depends(require_permission("roles.manage")),
) -> None:
    target = get_role(db, role_code)
    if target.is_system:
        raise HTTPException(status_code=409, detail="预设角色不能删除")
    assigned_count = db.scalar(
        select(func.count(UserRole.user_id)).where(UserRole.role_code == role_code)
    ) or db.scalar(select(func.count(User.id)).where(User.role == role_code))
    if assigned_count:
        raise HTTPException(status_code=409, detail="该角色仍有关联账号，不能删除")
    add_audit_log(
        db,
        action="role_delete",
        resource=f"role:{target.code}",
        request=request,
        user=operator,
        detail={"target_name": target.name},
    )
    db.delete(target)
    db.commit()


@router.get("/audit")
def list_audit_logs(
    keyword: str = "",
    action: str = "",
    limit: int = Query(default=100, ge=1, le=300),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("audit.view")),
) -> list[dict[str, object]]:
    statement = select(AuditLog).options(selectinload(AuditLog.user))
    if action:
        statement = statement.where(AuditLog.action == action)
    if keyword.strip():
        term = f"%{keyword.strip()}%"
        statement = statement.where(
            or_(
                AuditLog.resource.like(term),
                AuditLog.detail.like(term),
                AuditLog.action.like(term),
            )
        )
    rows = db.scalars(statement.order_by(AuditLog.created_at.desc()).limit(limit)).all()
    return [
        {
            "id": row.id,
            "operator_name": row.user.display_name if row.user else "系统/未知账号",
            "action": row.action,
            "resource": row.resource,
            "detail": row.detail or "",
            "ip_address": row.ip_address or "",
            "created_at": row.created_at.isoformat() if row.created_at else "",
        }
        for row in rows
    ]
