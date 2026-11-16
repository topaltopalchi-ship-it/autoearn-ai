import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    from app import main
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "economics-api.db")
    monkeypatch.setenv("AUTOEARN_MASTER_PASSWORD", "test-owner-password")
    monkeypatch.setenv("AUTOEARN_AUTH_SECRET", "test-auth-secret")
    main.init_db()
    with TestClient(app, client=("127.0.0.1", 12345)) as test_client:
        response = test_client.post("/api/auth/login", json={"password": "test-owner-password"})
        assert response.status_code == 200
        yield test_client


def test_economics_endpoint_returns_net_hourly_and_target_comparison(client):
    response = client.post("/api/opportunities/evaluate", json={
        "gross_reward": 100,
        "estimated_hours": 4,
        "estimated_cost": 10,
        "fee_percent": 5,
        "flat_fee": 2,
        "currency": "EUR",
        "target_hourly_rate": 15,
    })
    assert response.status_code == 200
    result = response.json()
    assert result["estimated_net"] == 83
    assert result["estimated_net_per_hour"] == 20.75
    assert result["target_met"] is True
    assert result["assessment"] == "positive"
    assert result["verified"] is False


def test_economics_endpoint_rejects_mixed_currencies(client):
    response = client.post("/api/opportunities/evaluate", json={
        "gross_reward": 100,
        "estimated_hours": 4,
        "estimated_cost": 10,
        "currency": "EUR",
        "cost_currency": "USD",
    })
    assert response.status_code == 422


def test_economics_endpoint_rejects_invalid_hours_and_fee(client):
    assert client.post("/api/opportunities/evaluate", json={
        "gross_reward": 10, "estimated_hours": 0
    }).status_code == 422
    assert client.post("/api/opportunities/evaluate", json={
        "gross_reward": 10, "estimated_hours": 1, "fee_percent": 101
    }).status_code == 422
