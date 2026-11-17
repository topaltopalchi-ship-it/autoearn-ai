import pytest
import sqlite3
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    from app import main
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "test.db")
    main.init_db()
    with TestClient(app) as test_client:
        yield test_client


def opportunity(client):
    response = client.post("/api/opportunities", json={
        "title": "Puzzle rewards", "platform": "Example Games",
        "url": "https://example.com/game", "reward_description": "Points",
        "eligibility": "Available in eligible regions",
        "terms_url": "https://example.com/terms"
    })
    assert response.status_code == 201
    return response.json()


def test_health(client):
    assert client.get("/api/health").json()["status"] == "ok"


def test_opportunity_and_dashboard(client):
    opportunity(client)
    data = client.get("/api/dashboard").json()
    assert data["opportunities"] == 1
    assert data["awaiting_approval"] == 0


def test_task_requires_human_approval_before_completion(client):
    opp = opportunity(client)
    task = client.post("/api/tasks", json={
        "opportunity_id": opp["id"], "description": "Complete the daily puzzle manually"
    }).json()
    assert task["status"] == "pending_approval"
    assert client.post(f"/api/tasks/{task['id']}/complete").status_code == 409
    assert client.post(f"/api/tasks/{task['id']}/approve").status_code == 200
    assert client.post(f"/api/tasks/{task['id']}/complete").json()["status"] == "completed"


def test_rejects_non_http_url(client):
    response = client.post("/api/opportunities", json={
        "title": "Bad link", "platform": "Example", "url": "javascript:alert(1)"
    })
    assert response.status_code == 422


def test_reward_ledger(client):
    opp = opportunity(client)
    response = client.post("/api/rewards", json={
        "opportunity_id": opp["id"], "amount": 4.5, "currency": "USD", "status": "paid"
    })
    assert response.status_code == 201
    assert client.get("/api/dashboard").json()["paid_total"] == 4.5


def test_duplicate_opportunity_url_is_rejected(client):
    payload = {
        "title": "Puzzle rewards", "platform": "Example Games",
        "url": "https://example.com/game"
    }
    assert client.post("/api/opportunities", json=payload).status_code == 201
    duplicate = client.post("/api/opportunities", json=payload)
    assert duplicate.status_code == 409
    assert "already registered" in duplicate.json()["detail"]


def test_normalizes_duplicate_urls(client):
    payload = {
        "title": "Normalized URL", "platform": "Example Games",
        "url": "https://EXAMPLE.com/game/#tracking",
    }
    assert client.post("/api/opportunities", json=payload).status_code == 201
    duplicate = client.post("/api/opportunities", json={
        **payload, "title": "Same destination", "url": "https://example.com/game/"
    })
    assert duplicate.status_code == 409


def test_opportunity_score_is_out_of_100(client):
    response = client.post("/api/opportunities", json={
        "title": "Fully documented", "platform": "Example",
        "url": "https://example.com/game",
        "reward_description": "Points",
        "eligibility": "Eligible regions",
        "terms_url": "https://example.com/terms",
        "notes": "Reviewed manually",
    })
    assert response.status_code == 201
    assert response.json()["score"] == 100


def test_opportunity_records_region_and_payout_requirements(client):
    response = client.post("/api/opportunities", json={
        "title": "Regional rewards", "platform": "Example",
        "url": "https://example.com/regional",
        "eligible_countries": ["Germany", " France ", "Germany", ""],
        "excluded_countries": ["United States"],
        "minimum_withdrawal_amount": 10,
        "withdrawal_currency": "eur",
        "payout_methods": ["PayPal", "Bank transfer", "PayPal"],
    })
    assert response.status_code == 201
    item = response.json()
    assert item["eligible_countries"] == ["Germany", "France"]
    assert item["excluded_countries"] == ["United States"]
    assert item["minimum_withdrawal_amount"] == 10
    assert item["withdrawal_currency"] == "EUR"
    assert item["payout_methods"] == ["PayPal", "Bank transfer"]

    listed = client.get("/api/opportunities").json()
    assert listed[0]["payout_methods"] == ["PayPal", "Bank transfer"]


def test_opportunity_defaults_region_and_payout_fields(client):
    response = client.post("/api/opportunities", json={
        "title": "Basic source", "platform": "Example",
        "url": "https://example.com/basic",
    })
    assert response.status_code == 201
    item = response.json()
    assert item["eligible_countries"] == []
    assert item["excluded_countries"] == []
    assert item["minimum_withdrawal_amount"] is None
    assert item["withdrawal_currency"] == "USD"
    assert item["payout_methods"] == []


def test_negative_minimum_withdrawal_is_rejected(client):
    response = client.post("/api/opportunities", json={
        "title": "Invalid threshold", "platform": "Example",
        "url": "https://example.com/invalid",
        "minimum_withdrawal_amount": -1,
    })
    assert response.status_code == 422


def test_opportunity_requires_explicit_human_verification(client):
    item = opportunity(client)
    assert item["verification_status"] == "pending"
    assert item["verified_at"] is None

    verified = client.patch(f"/api/opportunities/{item['id']}/verification", json={
        "status": "verified", "notes": "Terms and country restrictions checked manually"
    })
    assert verified.status_code == 200
    result = verified.json()
    assert result["verification_status"] == "verified"
    assert result["verified_at"]
    assert result["verification_notes"].startswith("Terms and country")

    rejected = client.patch(f"/api/opportunities/{item['id']}/verification", json={
        "status": "rejected", "notes": "Payout terms could not be confirmed"
    })
    assert rejected.status_code == 200
    assert rejected.json()["verification_status"] == "rejected"
    assert rejected.json()["verified_at"] is None


def test_verification_endpoint_rejects_unknown_status(client):
    item = opportunity(client)
    response = client.patch(f"/api/opportunities/{item['id']}/verification", json={
        "status": "probably_legit"
    })
    assert response.status_code == 422


def test_verification_returns_404_for_missing_opportunity(client):
    response = client.patch("/api/opportunities/9999/verification", json={
        "status": "verified"
    })
    assert response.status_code == 404


def test_opportunities_can_be_filtered_by_verification_status(client):
    item = opportunity(client)
    assert len(client.get("/api/opportunities?verification_status=pending").json()) == 1
    client.patch(f"/api/opportunities/{item['id']}/verification", json={
        "status": "verified", "notes": "Manually checked"
    })
    assert client.get("/api/opportunities?verification_status=pending").json() == []
    verified = client.get("/api/opportunities?verification_status=verified").json()
    assert len(verified) == 1
    assert verified[0]["id"] == item["id"]


def test_existing_database_gets_verification_columns(tmp_path, monkeypatch):
    from app import main

    legacy_db = tmp_path / "legacy.db"
    monkeypatch.setattr(main, "DB_PATH", legacy_db)
    with sqlite3.connect(legacy_db) as db:
        db.execute("""
            CREATE TABLE opportunities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                platform TEXT NOT NULL,
                url TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'game',
                reward_description TEXT NOT NULL DEFAULT '',
                eligibility TEXT NOT NULL DEFAULT '',
                terms_url TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'discovered',
                score INTEGER NOT NULL DEFAULT 0,
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            )
        """)
    main.init_db()
    with sqlite3.connect(legacy_db) as db:
        columns = {row[1] for row in db.execute("PRAGMA table_info(opportunities)")}
    assert {"eligible_countries", "payout_methods", "verification_status",
            "verified_at", "verification_notes"}.issubset(columns)
