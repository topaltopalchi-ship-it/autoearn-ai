import pytest
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


def test_automation_policy_fails_closed_for_unknown_or_captcha():
    from app.policy import derive_automation_eligibility
    assert derive_automation_eligibility("unknown", None, "ordinary") == "manual_only"
    assert derive_automation_eligibility("allowed", True, "ordinary") == "manual_only"
    assert derive_automation_eligibility("prohibited", False, "ordinary") == "excluded"


def test_paid_lottery_and_betting_are_never_auto_eligible():
    from app.policy import derive_automation_eligibility
    for category in ("paid_lottery", "betting"):
        assert derive_automation_eligibility("allowed", False, category) == "manual_only"


def test_free_giveaway_and_skill_contest_require_explicit_policy_clearance():
    from app.policy import derive_automation_eligibility
    assert derive_automation_eligibility("allowed", False, "giveaway_free") == "auto"
    assert derive_automation_eligibility("allowed", False, "skill_contest") == "auto"
    assert derive_automation_eligibility("unknown", False, "giveaway_free") == "manual_only"


def test_opportunity_policy_metadata_and_auto_eligible_filter(client):
    auto = client.post("/api/opportunities", json={
        "title": "Free skill contest", "platform": "Example",
        "url": "https://policy-auto.example/contest",
        "automation_policy": "allowed", "captcha_required": False,
        "opportunity_category": "skill_contest",
        "policy_source": "terms", "policy_evidence_url": "https://policy-auto.example/terms",
    })
    unknown = client.post("/api/opportunities", json={
        "title": "Unknown giveaway", "platform": "Example",
        "url": "https://policy-unknown.example/giveaway",
        "opportunity_category": "giveaway_free",
    })
    blocked = client.post("/api/opportunities", json={
        "title": "No bots", "platform": "Example",
        "url": "https://policy-blocked.example/offer",
        "automation_policy": "prohibited", "captcha_required": False,
    })
    assert auto.status_code == unknown.status_code == blocked.status_code == 201
    assert auto.json()["automation_eligibility"] == "auto"
    assert unknown.json()["automation_eligibility"] == "manual_only"
    assert blocked.json()["automation_eligibility"] == "excluded"
    eligible = client.get("/api/opportunities/automation-eligible").json()
    assert [item["id"] for item in eligible] == [auto.json()["id"]]


def test_policy_evidence_url_must_be_http(client):
    response = client.post("/api/opportunities", json={
        "title": "Invalid policy evidence", "platform": "Example",
        "url": "https://policy-invalid.example",
        "policy_evidence_url": "javascript:alert(1)",
    })
    assert response.status_code == 422


def test_existing_opportunities_receive_safe_policy_defaults(tmp_path, monkeypatch):
    import sqlite3
    from app import main
    db_path = tmp_path / "legacy.db"
    monkeypatch.setattr(main, "DB_PATH", db_path)
    with sqlite3.connect(db_path) as db:
        db.execute("""
            CREATE TABLE opportunities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL, platform TEXT NOT NULL, url TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'game', reward_description TEXT NOT NULL DEFAULT '',
                eligibility TEXT NOT NULL DEFAULT '', terms_url TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'discovered', score INTEGER NOT NULL DEFAULT 0,
                notes TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL
            )
        """)
        db.execute("""
            INSERT INTO opportunities (title, platform, url, created_at)
            VALUES ('Legacy opportunity', 'Example', 'https://legacy.example', 'old')
        """)
    main.init_db()
    with sqlite3.connect(db_path) as db:
        row = db.execute(
            "SELECT automation_policy, captcha_required, opportunity_category, automation_eligibility "
            "FROM opportunities WHERE id = 1"
        ).fetchone()
    assert row == ("unknown", None, "ordinary", "manual_only")
