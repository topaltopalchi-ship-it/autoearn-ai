from __future__ import annotations

import hashlib
import hmac
import os
import time
from collections import deque
from threading import Lock
from typing import Final

COOKIE_NAME: Final = "autoearn_session"
SESSION_MAX_AGE = 12 * 60 * 60
LOGIN_FAILURE_LIMIT = 5
LOGIN_WINDOW_SECONDS = 15 * 60

_login_failures: dict[str, deque[float]] = {}
_login_lock = Lock()


def _secret() -> bytes:
    value = os.getenv("AUTOEARN_AUTH_SECRET", "").strip()
    return value.encode("utf-8") if value else b""


def configured() -> bool:
    return bool(os.getenv("AUTOEARN_MASTER_PASSWORD", "").strip() and _secret())


def verify_password(password: str) -> bool:
    expected = os.getenv("AUTOEARN_MASTER_PASSWORD", "")
    return bool(expected) and hmac.compare_digest(password, expected)


def login_retry_after(client_key: str) -> int:
    """Return remaining lockout seconds for a client, or zero when allowed."""
    current = time.monotonic()
    with _login_lock:
        attempts = _login_failures.get(client_key)
        if attempts is None:
            return 0
        while attempts and current - attempts[0] >= LOGIN_WINDOW_SECONDS:
            attempts.popleft()
        if not attempts:
            _login_failures.pop(client_key, None)
            return 0
        if len(attempts) < LOGIN_FAILURE_LIMIT:
            return 0
        return max(1, int(LOGIN_WINDOW_SECONDS - (current - attempts[0]) + 0.999))


def record_login_failure(client_key: str) -> None:
    """Record one failed attempt in the in-memory, per-client sliding window."""
    current = time.monotonic()
    with _login_lock:
        attempts = _login_failures.setdefault(client_key, deque())
        while attempts and current - attempts[0] >= LOGIN_WINDOW_SECONDS:
            attempts.popleft()
        attempts.append(current)


def clear_login_failures(client_key: str) -> None:
    """Clear the client's failure window after a successful login."""
    with _login_lock:
        _login_failures.pop(client_key, None)


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
