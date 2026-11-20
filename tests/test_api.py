from fastapi.testclient import TestClient

from app.main import app


def test_health():
    with TestClient(app) as client:
        response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_home_serves_owner_login_and_static_assets():
    with TestClient(app) as client:
        response = client.get("/")
        css = client.get("/styles.css")
        config = client.get("/config.js")
        app_script = client.get("/app.js")
    assert response.status_code == 200
    assert 'id="auth-form"' in response.text
    assert "Sign in" in response.text
    assert "Sign up" not in response.text
    assert css.status_code == 200 and "body" in css.text
    assert config.status_code == 200 and "AUTOEARN_CONFIG" in config.text
    assert app_script.status_code == 200 and "loadData" in app_script.text


def test_legacy_unauthenticated_sqlite_api_is_not_exposed():
    with TestClient(app) as client:
        get_response = client.get("/api/opportunities")
        post_response = client.post("/api/opportunities", json={"title": "Test"})
    assert get_response.status_code == 404
    assert post_response.status_code == 404
