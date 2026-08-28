"""Helpers for consistent audit records."""

import json

from fastapi import Request
from sqlalchemy.orm import Session

from app.models.user import AuditLog, User


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def add_audit_log(
    db: Session,
    *,
    action: str,
    resource: str,
    request: Request,
    user: User | None = None,
    detail: dict[str, object] | str | None = None,
) -> None:
    if isinstance(detail, dict):
        detail_text = json.dumps(detail, ensure_ascii=False, separators=(",", ":"))
    else:
        detail_text = detail
    db.add(
        AuditLog(
            user_id=user.id if user else None,
            action=action,
            resource=resource,
            detail=detail_text,
            ip_address=client_ip(request),
        )
    )
