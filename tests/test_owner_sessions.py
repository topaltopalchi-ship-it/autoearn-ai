import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from app.main import app


PASSWORD = "correct-horse-battery-staple"


@pytest.fixture()
def owner_client(tmp_path, monkeypatch):
    from app import main
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "owner-auth.db")
    monkeypatch.setattr(main, "OWNER_TOKEN", "legacy-api-token-for-test-only-long-enough")
    monkeypatch.setattr(main, "OWNER_SESSION_SECURE", True)
    main.init_db()
    main.initialize_owner_password(PASSWORD)
    with TestClient(
        app,
        base_url="https://testserver",
        headers={"Origin": "https://testserver"},
    ) as client:
        yield client


def login(client, password=PASSWORD):
    return client.post("/api/auth/login", json={"password": password})


def csrf(client):
    response = client.get("/api/auth/session")
    assert response.status_code == 200
    return response.json()["csrf_token"]


def test_owner_password_login_issues_secure_httponly_cookie(owner_client):
    response = login(owner_client)
    assert response.status_code == 200
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "secure" in cookie
    assert "samesite=strict" in cookie
    assert response.json()["authenticated"] is True
    assert len(response.json()["csrf_token"]) >= 32


def test_password_is_argon2_hash_and_never_plaintext_in_database(owner_client):
    from app import main
    with main.connect() as db:
        row = db.execute("SELECT password_hash FROM owner_credentials WHERE id=1").fetchone()
    assert row["password_hash"].startswith("$argon2id$")
    assert PASSWORD not in row["password_hash"]


def test_invalid_password_is_rejected_and_rate_limited(owner_client):
    for _ in range(10):
        assert login(owner_client, "incorrect-password").status_code == 401
    limited = login(owner_client, "incorrect-password")
    assert limited.status_code == 429
    assert limited.headers["retry-after"] == "300"


def test_owner_api_requires_session_cookie_not_legacy_browser_storage(owner_client):
    assert owner_client.get("/api/opportunities").status_code == 401
    assert login(owner_client).status_code == 200
    assert owner_client.get("/api/opportunities").status_code == 200


def test_state_changing_session_request_requires_csrf(owner_client):
    assert login(owner_client).status_code == 200
    response = owner_client.post("/api/opportunities", json={
        "title": "Protected", "platform": "Example", "url": "https://example.com/protected"
    })
    assert response.status_code == 403
    accepted = owner_client.post(
        "/api/opportunities",
        headers={"X-CSRF-Token": csrf(owner_client)},
        json={"title": "Protected", "platform": "Example", "url": "https://example.com/protected"},
    )
    assert accepted.status_code == 201


def test_session_mutations_reject_cross_origin_requests(owner_client):
    assert login(owner_client).status_code == 200
    response = owner_client.post(
        "/api/opportunities",
        headers={"Origin": "https://attacker.example", "X-CSRF-Token": csrf(owner_client)},
        json={"title": "Blocked", "platform": "Example", "url": "https://example.com/blocked"},
    )
    assert response.status_code == 403


def test_session_expires_after_thirty_minutes_idle(owner_client, monkeypatch):
    from app import main
    current = [datetime(2026, 1, 1, tzinfo=timezone.utc)]
    monkeypatch.setattr(main, "_owner_auth_now", lambda: current[0])
    assert login(owner_client).status_code == 200
    current[0] += timedelta(minutes=31)
    assert owner_client.get("/api/opportunities").status_code == 401


def test_new_login_revokes_previous_session(owner_client):
    assert login(owner_client).status_code == 200
    first_cookie = owner_client.cookies.get(main_cookie_name())
    assert login(owner_client).status_code == 200
    assert owner_client.get("/api/opportunities").status_code == 200
    with TestClient(app, base_url="https://testserver") as old_client:
        old_client.cookies.set(main_cookie_name(), first_cookie, domain="testserver", path="/")
        assert old_client.get("/api/opportunities").status_code == 401


def main_cookie_name():
    from app.main import OWNER_SESSION_COOKIE
    return OWNER_SESSION_COOKIE


def test_logout_revokes_server_side_session(owner_client):
    assert login(owner_client).status_code == 200
    response = owner_client.post("/api/auth/logout", headers={"X-CSRF-Token": csrf(owner_client)})
    assert response.status_code == 200
    assert owner_client.get("/api/opportunities").status_code == 401


def test_password_reset_revokes_existing_sessions(owner_client):
    from app import main
    assert login(owner_client).status_code == 200
    main.initialize_owner_password("a-different-long-owner-password")
    assert owner_client.get("/api/opportunities").status_code == 401
    assert login(owner_client, "a-different-long-owner-password").status_code == 200


def test_owner_password_rejects_short_values(owner_client):
    from app import main
    with pytest.raises(ValueError):
        main.initialize_owner_password("short")
