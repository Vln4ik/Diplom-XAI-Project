from __future__ import annotations

import base64
import hashlib
import hmac
import os
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from app.core.config import get_settings

PBKDF2_ROUNDS = 390_000


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ROUNDS)
    return f"pbkdf2_sha256${PBKDF2_ROUNDS}${base64.urlsafe_b64encode(salt).decode()}${base64.urlsafe_b64encode(digest).decode()}"


def verify_password(password: str, password_hash: str) -> bool:
    algorithm, rounds_raw, salt_raw, digest_raw = password_hash.split("$", maxsplit=3)
    if algorithm != "pbkdf2_sha256":
        return False
    rounds = int(rounds_raw)
    salt = base64.urlsafe_b64decode(salt_raw.encode())
    expected = base64.urlsafe_b64decode(digest_raw.encode())
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, rounds)
    return hmac.compare_digest(candidate, expected)


def create_token(subject: str, token_type: str, expires_delta: timedelta, extra: dict[str, Any] | None = None) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def create_access_token(subject: str) -> str:
    settings = get_settings()
    return create_token(subject, "access", timedelta(minutes=settings.access_token_ttl_minutes))


def create_refresh_token(subject: str) -> str:
    settings = get_settings()
    return create_token(subject, "refresh", timedelta(minutes=settings.refresh_token_ttl_minutes))


def decode_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    return jwt.decode(token, settings.secret_key, algorithms=["HS256"])
