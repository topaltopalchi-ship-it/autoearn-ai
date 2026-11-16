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


def test_opportunity_score_is_bounded_and_reflects_missing_optional_details(client):
    response = client.post("/api/opportunities", json={
        "title": "Partially documented", "platform": "Example",
        "url": "https://example.com/partial",
    })
    assert response.status_code == 201
    assert 0 <= response.json()["score"] <= 100
    assert response.json()["score"] == 20


def test_api_canonicalizes_case_tracking_and_trailing_slash(client):
    first = client.post("/api/opportunities", json={
        "title": "Canonical URL", "platform": "Example",
        "url": "HTTPS://EXAMPLE.COM/rewards/?utm_source=mail&gclid=abc",
    })
    assert first.status_code == 201
    assert first.json()["url"] == "https://example.com/rewards"

    duplicate = client.post("/api/opportunities", json={
        "title": "Duplicate URL", "platform": "Example",
        "url": "https://example.com/rewards/",
    })
    assert duplicate.status_code == 409


def test_discover_requires_search_provider_configuration(client, monkeypatch):
    monkeypatch.delenv("BRAVE_SEARCH_API_KEY", raising=False)
    response = client.post("/api/discover", json={"query": "game rewards"})
    assert response.status_code == 503


def test_discover_returns_unverified_candidates_for_human_review(client, monkeypatch):
    from app import main
    from autoearn.opportunities import SearchResult

    class FakeProvider:
        def search(self, query, limit=10):
            assert query == "game rewards"
            assert limit == 3
            return [SearchResult(
                title="Rewards program terms",
                url="https://example.com/rewards",
                snippet="Eligibility and points details",
                provider="test",
            )]

    monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "test-token")
    monkeypatch.setattr(main, "BraveSearchProvider", lambda token: FakeProvider())
    response = client.post("/api/discover", json={"query": "game rewards", "limit": 3})

    assert response.status_code == 200
    candidate = response.json()[0]
    assert candidate["domain"] == "example.com"
    assert candidate["verified"] is False
    assert candidate["review_required"] is True
    assert "reward_language_found" in candidate["signals"]


def test_discover_rejects_invalid_limit(client):
    response = client.post("/api/discover", json={"query": "game rewards", "limit": 99})
    assert response.status_code == 422
