from fastapi.testclient import TestClient

from app.main import app


def test_health():
    with TestClient(app) as client:
        response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_home_serves_owner_login():
    with TestClient(app) as client:
        response = client.get("/")
    assert response.status_code == 200
    assert 'id="auth-form"' in response.text
    assert "Sign in" in response.text
    assert "Sign up" not in response.text


def test_legacy_unauthenticated_sqlite_api_is_not_exposed():
    with TestClient(app) as client:
        get_response = client.get("/api/opportunities")
        post_response = client.post("/api/opportunities", json={"title": "Test"})
    assert get_response.status_code == 404
    assert post_response.status_code == 404
