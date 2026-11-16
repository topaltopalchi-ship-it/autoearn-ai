from __future__ import annotations

import hashlib
import hmac
import os
import time
from typing import Final

COOKIE_NAME: Final = "autoearn_session"
SESSION_MAX_AGE = 12 * 60 * 60


def _secret() -> bytes:
    value = os.getenv("AUTOEARN_AUTH_SECRET", "").strip()
    return value.encode("utf-8") if value else b""


def configured() -> bool:
    return bool(os.getenv("AUTOEARN_MASTER_PASSWORD", "").strip() and _secret())


def verify_password(password: str) -> bool:
    expected = os.getenv("AUTOEARN_MASTER_PASSWORD", "")
    return bool(expected) and hmac.compare_digest(password, expected)


def issue_session() -> str:
    timestamp = str(int(time.time()))
    signature = hmac.new(_secret(), timestamp.encode(), hashlib.sha256).hexdigest()
    return f"{timestamp}.{signature}"


def valid_session(value: str | None) -> bool:
    if not value or not configured():
        return False
    try:
        timestamp, signature = value.split(".", 1)
        issued = int(timestamp)
    except (ValueError, AttributeError):
        return False
    if issued > int(time.time()) or int(time.time()) - issued > SESSION_MAX_AGE:
        return False
    expected = hmac.new(_secret(), timestamp.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, expected)
