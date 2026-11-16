from fastapi.testclient import TestClient

from app import auth
from app.main import app


def test_login_locks_after_five_failed_attempts(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(auth.time, "monotonic", lambda: now[0])
    key = "127.0.0.1"

    for _ in range(auth.LOGIN_FAILURE_LIMIT):
        assert auth.login_retry_after(key) == 0
        auth.record_login_failure(key)

    assert auth.login_retry_after(key) == auth.LOGIN_WINDOW_SECONDS
    now[0] += 60
    assert auth.login_retry_after(key) == auth.LOGIN_WINDOW_SECONDS - 60


def test_login_window_expires_and_allows_new_attempts(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(auth.time, "monotonic", lambda: now[0])
    key = "127.0.0.1"

    for _ in range(auth.LOGIN_FAILURE_LIMIT):
        auth.record_login_failure(key)
    assert auth.login_retry_after(key) > 0

    now[0] += auth.LOGIN_WINDOW_SECONDS
    assert auth.login_retry_after(key) == 0


def test_successful_login_clears_failure_history(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(auth.time, "monotonic", lambda: now[0])
    key = "127.0.0.1"

    for _ in range(auth.LOGIN_FAILURE_LIMIT):
        auth.record_login_failure(key)
    auth.clear_login_failures(key)
    assert auth.login_retry_after(key) == 0


def test_login_endpoint_returns_429_and_retry_after_header(tmp_path, monkeypatch):
    from app import main

    monkeypatch.setenv("AUTOEARN_MASTER_PASSWORD", "test-owner-password")
    monkeypatch.setenv("AUTOEARN_AUTH_SECRET", "test-auth-secret")
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "login-rate-limit.db")
    monkeypatch.setattr(auth, "_login_failures", {})
    with TestClient(app, client=("127.0.0.1", 12345)) as client:
        for _ in range(auth.LOGIN_FAILURE_LIMIT):
            response = client.post("/api/auth/login", json={"password": "wrong"})
            assert response.status_code == 401

        blocked = client.post("/api/auth/login", json={"password": "test-owner-password"})
        assert blocked.status_code == 429
        assert int(blocked.headers["Retry-After"]) > 0
