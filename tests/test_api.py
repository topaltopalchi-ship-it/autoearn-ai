import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    from app import main
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setenv("AUTOEARN_MASTER_PASSWORD", "test-owner-password")
    monkeypatch.setenv("AUTOEARN_AUTH_SECRET", "test-auth-secret")
    main.init_db()
    with TestClient(app, client=("127.0.0.1", 12345)) as test_client:
        login = test_client.post("/api/auth/login", json={"password": "test-owner-password"})
        assert login.status_code == 200
        yield test_client


def test_auth_rejects_wrong_password(tmp_path, monkeypatch):
    from app import main
    monkeypatch.setenv("AUTOEARN_MASTER_PASSWORD", "test-owner-password")
    monkeypatch.setenv("AUTOEARN_AUTH_SECRET", "test-auth-secret")
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "auth.db")
    main.init_db()
    with TestClient(app, client=("127.0.0.1", 12345)) as test_client:
        assert test_client.post("/api/auth/login", json={"password": "wrong"}).status_code == 401


def test_auth_requires_configuration(tmp_path, monkeypatch):
    from app import main
    monkeypatch.delenv("AUTOEARN_MASTER_PASSWORD", raising=False)
    monkeypatch.delenv("AUTOEARN_AUTH_SECRET", raising=False)
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "unconfigured-auth.db")
    main.init_db()
    with TestClient(app, client=("127.0.0.1", 12345)) as test_client:
        response = test_client.get("/api/opportunities")
        assert response.status_code == 503


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


def test_terms_url_rejects_credentials_and_local_hosts(client):
    base = {
        "title": "Terms safety", "platform": "Example",
        "url": "https://example.com/reward",
    }
    for terms_url in (
        "https://user:password@example.com/terms",
        "http://127.0.0.1/terms",
        "http://localhost/terms",
        "javascript:alert(1)",
    ):
        response = client.post("/api/opportunities", json={**base, "terms_url": terms_url})
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


def test_discover_uses_mwmbl_adapter_when_no_keys_are_configured(client, monkeypatch):
    from app import main
    from autoearn.opportunities import SearchResult

    monkeypatch.delenv("BRAVE_SEARCH_API_KEY", raising=False)
    monkeypatch.delenv("MWMBL_API_KEY", raising=False)

    class FakeProvider:
        def search(self, query, limit=10):
            assert query.startswith("game rewards ")
            assert "surveys" in query and "freelance" in query
            return [SearchResult(
                title="Game rewards terms",
                url="https://example.com/rewards",
                snippet="Eligibility and payout details",
                provider="mwmbl",
            )]

    monkeypatch.setattr(main, "MwmblSearchProvider", lambda api_key=None: FakeProvider())
    response = client.post("/api/discover", json={"query": "game rewards"})

    assert response.status_code == 200
    assert response.json()[0]["provider"] == "mwmbl"
    assert response.json()[0]["verified"] is False
    assert response.json()[0]["review_required"] is True


def test_discover_passes_optional_mwmbl_api_key(client, monkeypatch):
    from app import main

    monkeypatch.delenv("BRAVE_SEARCH_API_KEY", raising=False)
    monkeypatch.setenv("MWMBL_API_KEY", "optional-test-key")
    seen = {}

    class FakeProvider:
        def __init__(self, api_key=None):
            seen["api_key"] = api_key

        def search(self, query, limit=10):
            return []

    monkeypatch.setattr(main, "MwmblSearchProvider", FakeProvider)
    response = client.post("/api/discover", json={"query": "game rewards"})

    assert response.status_code == 200
    assert seen["api_key"] == "optional-test-key"


def test_brave_provider_takes_precedence_when_configured(client, monkeypatch):
    from app import main

    monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "brave-test-key")
    monkeypatch.setenv("MWMBL_API_KEY", "mwmbl-test-key")
    seen = {}

    class FakeProvider:
        def search(self, query, limit=10):
            seen["called"] = True
            return []

    monkeypatch.setattr(main, "BraveSearchProvider", lambda token: FakeProvider())
    response = client.post("/api/discover", json={"query": "game rewards"})

    assert response.status_code == 200
    assert seen["called"] is True


def test_discover_returns_unverified_candidates_for_human_review(client, monkeypatch):
    from app import main
    from autoearn.opportunities import SearchResult

    class FakeProvider:
        def search(self, query, limit=10):
            assert query.startswith("game rewards ")
            assert "surveys" in query and "freelance" in query
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


def test_discover_persists_deduplicated_review_inbox(client, monkeypatch):
    from app import main
    from autoearn.opportunities import SearchResult

    class FakeProvider:
        def search(self, query, limit=10):
            return [SearchResult(
                title="Cashback rewards",
                url="https://example.net/rewards?utm_source=feed",
                snippet="Read eligibility and terms",
                provider="test",
            )]

    monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "test-token")
    monkeypatch.setattr(main, "BraveSearchProvider", lambda token: FakeProvider())
    payload = {"query": "cashback programs", "limit": 5}

    first = client.post("/api/discover", json=payload)
    second = client.post("/api/discover", json=payload)
    inbox = client.get("/api/discoveries")

    assert first.status_code == second.status_code == 200
    assert first.json()[0]["is_new"] is True
    assert second.json()[0]["is_new"] is False
    assert len(inbox.json()) == 1
    assert inbox.json()[0]["url"] == "https://example.net/rewards"
    assert inbox.json()[0]["review_required"] is True
    assert inbox.json()[0]["verified"] is False


def test_discovery_candidate_human_review_is_persisted_but_not_verified(client, monkeypatch):
    from app import main
    from autoearn.opportunities import SearchResult

    class FakeProvider:
        def search(self, query, limit=10):
            return [SearchResult("Cashback terms", "https://example.org/cashback")]

    monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "test-token")
    monkeypatch.setattr(main, "BraveSearchProvider", lambda token: FakeProvider())
    candidate = client.post("/api/discover", json={"query": "cashback", "limit": 1}).json()[0]
    response = client.patch(
        f"/api/discoveries/{candidate['id']}/review",
        json={"status": "accepted", "note": "Check eligibility manually."},
    )
    assert response.status_code == 200
    assert response.json()["review_status"] == "accepted"
    assert response.json()["review_note"] == "Check eligibility manually."
    assert response.json()["verified"] is False
    assert response.json()["review_required"] is True
    assert client.get("/api/discoveries").json()[0]["review_status"] == "accepted"
    # Accepting a candidate is a triage decision only; it must not silently
    # activate the candidate as a vetted opportunity.
    assert client.get("/api/opportunities").json() == []


def test_discovery_review_validates_status_and_candidate_id(client):
    assert client.patch("/api/discoveries/999/review", json={"status": "accepted"}).status_code == 404
    assert client.patch("/api/discoveries/999/review", json={"status": "pending"}).status_code == 422


def test_discovery_categories_endpoint_lists_broad_catalog(client):
    categories = client.get("/api/discovery-categories").json()
    ids = {item["id"] for item in categories}
    assert {"games", "surveys", "user_testing", "microtasks", "freelance",
            "cashback", "affiliate", "creator", "tutoring", "digital_products",
            "research", "bug_bounty"} <= ids


def test_risk_assessment_endpoint_returns_explainable_flags(client):
    response = client.post("/api/risk-assessments", json={
        "upfront_payment": True,
        "deposit_or_top_up": True,
        "unclear_or_missing_terms": True,
    })
    assert response.status_code == 200
    result = response.json()
    assert result["risk_score"] == 55
    assert result["risk_level"] == "high"
    assert result["requires_human_review"] is True
    assert result["verified"] is False


def test_discovery_category_is_persisted(client, monkeypatch):
    from app import main

    class FakeProvider:
        def search(self, query, limit=10):
            assert "website app usability testing" in query
            return [{
                "title": "Website tester",
                "url": "https://example.com/tester",
                "snippet": "Paid website testing",
                "provider": "fixture",
            }]

    monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "test-token")
    monkeypatch.setattr(main, "BraveSearchProvider", lambda token: FakeProvider())
    response = client.post("/api/discover", json={
        "query": "remote testing", "category": "user_testing"
    })
    assert response.status_code == 200
    assert response.json()[0]["category"] == "user_testing"
    assert client.get("/api/discoveries").json()[0]["category"] == "user_testing"


def test_ranked_opportunities_api_uses_saved_metadata_and_country(tmp_path, monkeypatch):
    from app import main
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "ranking-api.db")
    main.init_db()
    with TestClient(app, client=("127.0.0.1", 12345)) as test_client:
        response = test_client.post("/api/opportunities", json={
            "title": "Remote task", "platform": "Example",
            "url": "https://example.org/task",
            "estimated_reward": 20, "reward_currency": "EUR",
            "estimated_hours": 2, "eligible_countries": "DE,AT",
            "payout_method": "Bank transfer", "minimum_payout": 5,
            "risk_score": 10
        })
        assert response.status_code == 201
        ranked = test_client.get("/api/opportunities/ranked?country=DE")
        assert ranked.status_code == 200
        item = ranked.json()[0]
        assert item["ranking"]["data_coverage"] == 100
        assert item["reward_currency"] == "EUR"
        outside = test_client.get("/api/opportunities/ranked?country=US").json()[0]
        assert outside["ranking"]["components"][2]["score"] == 0


def test_discoveries_ranked_endpoint_prioritizes_evidence_and_keeps_unverified(client, monkeypatch):
    from app import main
    from autoearn.opportunities import SearchResult

    class FakeProvider:
        def search(self, query, limit=10):
            return [
                SearchResult("Candidate with terms", "https://example.org/terms"),
                SearchResult("Candidate without details", "https://example.net/other"),
            ]

    monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "test-token")
    monkeypatch.setattr(main, "BraveSearchProvider", lambda token: FakeProvider())
    found = client.post("/api/discover", json={"query": "remote work", "limit": 2}).json()
    first_id = found[0]["id"]
    extracted = client.post(
        f"/api/discoveries/{first_id}/extract",
        json={"page_text": "Terms and conditions. Eligible residents of Germany receive EUR 10."},
    )
    assert extracted.status_code == 200
    assert extracted.json()["verified"] is False
    ranked = client.get("/api/discoveries/ranked?review_status=pending")
    assert ranked.status_code == 200
    items = ranked.json()
    assert len(items) == 2
    assert items[0]["id"] == first_id
    assert items[0]["review_priority"]["review_priority_score"] > items[1]["review_priority"]["review_priority_score"]
    assert all(item["verified"] is False for item in items)


def _insert_discovery_candidate(client, *, status="accepted", extraction=None, url="https://example.org/offer"):
    import json
    from app import main
    with main.connect() as db:
        cursor = db.execute(
            """
            INSERT INTO discovered_candidates
            (title, canonical_url, snippet, provider, domain, category, discovered_at,
             confidence, review_status, extraction_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("Personal survey offer", url, "Public description", "test", "example.org",
             "surveys", "2026-11-16T10:00:00+00:00", 70, status,
             json.dumps(extraction or {}), "2026-11-16T10:00:00+00:00"),
        )
        return cursor.lastrowid


@pytest.mark.parametrize("status", ["pending", "rejected"])
def test_promotion_requires_explicit_acceptance(client, status):
    candidate_id = _insert_discovery_candidate(client, status=status)
    response = client.post(f"/api/discoveries/{candidate_id}/promote")
    assert response.status_code == 409
    assert client.get("/api/opportunities").json() == []


def test_accepted_candidate_promotes_without_guessing_numeric_reward(client):
    candidate_id = _insert_discovery_candidate(
        client,
        extraction={
            "reward_amounts": [{"currency": "EUR", "amount_text": "10"}],
            "eligibility_evidence": ["Eligible residents of Germany."],
            "terms_mentioned": True,
            "verified": False,
            "disclaimer": "Extracted from supplied text only.",
        },
    )
    response = client.post(f"/api/discoveries/{candidate_id}/promote")
    assert response.status_code == 200
    result = response.json()
    opportunity = result["opportunity"]
    assert result["already_promoted"] is False
    assert opportunity["title"] == "Personal survey offer"
    assert opportunity["platform"] == "example.org"
    assert opportunity["category"] == "surveys"
    assert opportunity["url"] == "https://example.org/offer"
    assert "EUR 10" in opportunity["reward_description"]
    assert opportunity["estimated_reward"] is None
    assert opportunity["estimated_hours"] is None
    assert opportunity["eligible_countries"] == ""
    assert opportunity["payout_method"] == ""
    assert opportunity["minimum_payout"] is None
    assert opportunity["risk_score"] is None
    candidate = client.get("/api/discoveries").json()[0]
    assert candidate["review_status"] == "accepted"
    assert candidate["promoted_opportunity_id"] == opportunity["id"]


def test_promotion_is_idempotent_and_does_not_create_duplicates(client):
    candidate_id = _insert_discovery_candidate(client, status="accepted")
    first = client.post(f"/api/discoveries/{candidate_id}/promote")
    second = client.post(f"/api/discoveries/{candidate_id}/promote")
    assert first.status_code == second.status_code == 200
    assert second.json()["already_promoted"] is True
    assert first.json()["opportunity"]["id"] == second.json()["opportunity"]["id"]
    assert len(client.get("/api/opportunities").json()) == 1


def test_promotion_reuses_existing_opportunity_for_same_url(client):
    opportunity_response = client.post("/api/opportunities", json={
        "title": "Already tracked", "platform": "Example",
        "url": "https://example.org/offer",
    })
    candidate_id = _insert_discovery_candidate(client, status="accepted")
    response = client.post(f"/api/discoveries/{candidate_id}/promote")
    assert response.status_code == 200
    assert response.json()["already_exists"] is True
    assert response.json()["opportunity"]["id"] == opportunity_response.json()["id"]
    assert len(client.get("/api/opportunities").json()) == 1


def test_rejects_non_loopback_client_even_when_server_is_bound_externally(tmp_path, monkeypatch):
    from app import main
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "remote-client.db")
    main.init_db()
    with TestClient(app, client=("203.0.113.10", 54321)) as remote_client:
        response = remote_client.get("/api/health")
    assert response.status_code == 403
    assert response.json()["detail"] == "This personal app only accepts loopback connections."


def test_accepts_loopback_client(tmp_path, monkeypatch):
    from app import main
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "loopback-client.db")
    main.init_db()
    with TestClient(app, client=("127.0.0.1", 54321)) as local_client:
        response = local_client.get("/api/health")
    assert response.status_code == 200
