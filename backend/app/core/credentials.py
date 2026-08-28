"""Encryption helpers for administrator-only password recovery."""

from base64 import urlsafe_b64encode
from hashlib import sha256

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


def _fernet() -> Fernet:
    key = urlsafe_b64encode(sha256(settings.app_secret_key.encode("utf-8")).digest())
    return Fernet(key)


def encrypt_password(password: str) -> str:
    return _fernet().encrypt(password.encode("utf-8")).decode("ascii")


def decrypt_password(ciphertext: str | None) -> str | None:
    if not ciphertext:
        return None
    try:
        return _fernet().decrypt(ciphertext.encode("ascii")).decode("utf-8")
    except (InvalidToken, UnicodeDecodeError, ValueError):
        return None
