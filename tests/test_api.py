import pytest
import sqlite3
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    from app import main
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(main, "OWNER_TOKEN", "test-owner-secret-0123456789-abcdef")
    main.init_db()
    with TestClient(app) as test_client:
        yield test_client


def opportunity(client):
    response = client.post("/api/opportunities", headers={"X-AutoEarn-Owner-Token": "test-owner-secret-0123456789-abcdef"}, json={
        "title": "Puzzle rewards", "platform": "Example Games",
        "url": "https://example.com/game", "reward_description": "Points",
        "eligibility": "Available in eligible regions",
        "terms_url": "https://example.com/terms"
    })
    assert response.status_code == 201
    return response.json()


def test_health(client):
    assert client.get("/api/health").json()["status"] == "ok"


def test_source_intake_is_persistent_and_requires_human_review(client):
    response = client.post("/api/sources", headers={"X-AutoEarn-Owner-Token": "test-owner-secret-0123456789-abcdef"}, json={
        "name": "Example rewards", "url": "https://EXAMPLE.com/rewards/#tracking",
        "category": "Game_Rewards", "terms_url": "https://example.com/terms",
        "country_notes": "Germany only", "payment_notes": "PayPal terms to verify",
    })
    assert response.status_code == 201
    source = response.json()
    assert source["url"] == "https://example.com/rewards"
    assert source["category"] == "game_rewards"
    assert source["status"] == "pending"
    assert source["review_notes"] == ""

    listed = client.get("/api/sources?status=pending")
    assert listed.status_code == 200
    assert listed.json()[0]["id"] == source["id"]

    duplicate = client.post("/api/sources", headers={"X-AutoEarn-Owner-Token": "test-owner-secret-0123456789-abcdef"}, json={
        "name": "Duplicate source", "url": "https://example.com/rewards/"
    })
    assert duplicate.status_code == 409

    approved = client.patch(f"/api/sources/{source['id']}/review", headers={"X-AutoEarn-Owner-Token": "test-owner-secret-0123456789-abcdef"}, json={
        "status": "approved", "notes": "Public terms reviewed manually"
    })
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert approved.json()["review_notes"] == "Public terms reviewed manually"
    assert client.get("/api/sources?status=pending").json() == []


def test_source_intake_rejects_unsafe_terms_url(client):
    response = client.post("/api/sources", headers={"X-AutoEarn-Owner-Token": "test-owner-secret-0123456789-abcdef"}, json={
        "name": "Unsafe terms", "url": "https://example.com/source",
        "terms_url": "javascript:alert(1)",
    })
    assert response.status_code == 422


def test_source_review_returns_404_for_missing_source(client):
    response = client.patch("/api/sources/9999/review", headers={"X-AutoEarn-Owner-Token": "test-owner-secret-0123456789-abcdef"}, json={"status": "approved"})
    assert response.status_code == 404


def test_opportunity_and_dashboard(client):
    opportunity(client)
    data = client.get("/api/dashboard", headers={"X-AutoEarn-Owner-Token": "test-owner-secret-0123456789-abcdef"}).json()
    assert data["opportunities"] == 1
    assert data["awaiting_approval"] == 0


def test_task_requires_human_approval_before_completion(client):
    opp = opportunity(client)
    task = client.post("/api/tasks", headers={"X-AutoEarn-Owner-Token": "test-owner-secret-0123456789-abcdef"}, json={
        "opportunity_id": opp["id"], "description": "Complete the daily puzzle manually"
    }).json()
    assert task["status"] == "pending_approval"
    assert client.post(f"/api/tasks/{task['id']}/complete", headers={"X-AutoEarn-Owner-Token": "test-owner-secret-0123456789-abcdef"}).status_code == 409
    assert client.post(f"/api/tasks/{task['id']}/approve", headers={"X-AutoEarn-Owner-Token": "test-owner-secret-0123456789-abcdef"}).status_code == 200
    assert client.post(f"/api/tasks/{task['id']}/complete", headers={"X-AutoEarn-Owner-Token": "test-owner-secret-0123456789-abcdef"}).json()["status"] == "completed"


def test_rejects_non_http_url(client):
    response = client.post("/api/opportunities", headers={"X-AutoEarn-Owner-Token": "test-owner-secret-0123456789-abcdef"}, json={
        "title": "Bad link", "platform": "Example", "url": "javascript:alert(1)"
    })
    assert response.status_code == 422


def test_reward_ledger(client):
    opp = opportunity(client)
    response = client.post("/api/rewards", headers={"X-AutoEarn-Owner-Token": "test-owner-secret-0123456789-abcdef"}, json={
        "opportunity_id": opp["id"], "amount": 4.5, "currency": "USD", "status": "paid"
    })
    assert response.status_code == 201
    assert client.get("/api/dashboard", headers={"X-AutoEarn-Owner-Token": "test-owner-secret-0123456789-abcdef"}).json()["paid_total"] == 4.5


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
    duplicate = client.post("/api/opportunities", headers={"X-AutoEarn-Owner-Token": "test-owner-secret-0123456789-abcdef"}, json={
        **payload, "title": "Same destination", "url": "https://example.com/game/"
    })
    assert duplicate.status_code == 409


def test_opportunity_score_is_out_of_100(client):
    response = client.post("/api/opportunities", headers={"X-AutoEarn-Owner-Token": "test-owner-secret-0123456789-abcdef"}, json={
        "title": "Fully documented", "platform": "Example",
        "url": "https://example.com/game",
        "reward_description": "Points",
        "eligibility": "Eligible regions",
        "terms_url": "https://example.com/terms",
        "notes": "Reviewed manually",
    })
    assert response.status_code == 201
    assert response.json()["score"] == 100


def test_api_completeness_score_uses_documented_weights(client):
    base = {
        "title": "Scoring check", "platform": "Example",
        "url": "https://example.com/scoring",
    }
    terms_only = client.post("/api/opportunities", headers={"X-AutoEarn-Owner-Token": "test-owner-secret-0123456789-abcdef"}, json={
        **base, "terms_url": "https://example.com/terms"
    })
    assert terms_only.status_code == 201
    assert terms_only.json()["score"] == 40

    eligibility_only = client.post("/api/opportunities", headers={"X-AutoEarn-Owner-Token": "test-owner-secret-0123456789-abcdef"}, json={
        **base, "url": "https://example.com/eligibility",
        "eligibility": "Eligible regions"
    })
    assert eligibility_only.status_code == 201
    assert eligibility_only.json()["score"] == 30

    reward_only = client.post("/api/opportunities", headers={"X-AutoEarn-Owner-Token": "test-owner-secret-0123456789-abcdef"}, json={
        **base, "url": "https://example.com/reward",
        "reward_description": "Points"
    })
    assert reward_only.status_code == 201
    assert reward_only.json()["score"] == 30


def test_opportunity_records_region_and_payout_requirements(client):
    response = client.post("/api/opportunities", headers={"X-AutoEarn-Owner-Token": "test-owner-secret-0123456789-abcdef"}, json={
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
    response = client.post("/api/opportunities", headers={"X-AutoEarn-Owner-Token": "test-owner-secret-0123456789-abcdef"}, json={
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
    response = client.post("/api/opportunities", headers={"X-AutoEarn-Owner-Token": "test-owner-secret-0123456789-abcdef"}, json={
        "title": "Invalid threshold", "platform": "Example",
        "url": "https://example.com/invalid",
        "minimum_withdrawal_amount": -1,
    })
    assert response.status_code == 422


def test_opportunity_requires_explicit_human_verification(client):
    item = opportunity(client)
    assert item["verification_status"] == "pending"
    assert item["verified_at"] is None

    verified = client.patch(f"/api/opportunities/{item['id']}/verification", headers={"X-AutoEarn-Owner-Token": "test-owner-secret-0123456789-abcdef"}, json={
        "status": "verified", "notes": "Terms and country restrictions checked manually"
    })
    assert verified.status_code == 200
    result = verified.json()
    assert result["verification_status"] == "verified"
    assert result["verified_at"]
    assert result["verification_notes"].startswith("Terms and country")

    rejected = client.patch(f"/api/opportunities/{item['id']}/verification", headers={"X-AutoEarn-Owner-Token": "test-owner-secret-0123456789-abcdef"}, json={
        "status": "rejected", "notes": "Payout terms could not be confirmed"
    })
    assert rejected.status_code == 200
    assert rejected.json()["verification_status"] == "rejected"
    assert rejected.json()["verified_at"] is None


def test_verification_endpoint_rejects_unknown_status(client):
    item = opportunity(client)
    response = client.patch(f"/api/opportunities/{item['id']}/verification", headers={"X-AutoEarn-Owner-Token": "test-owner-secret-0123456789-abcdef"}, json={
        "status": "probably_legit"
    })
    assert response.status_code == 422


def test_verification_returns_404_for_missing_opportunity(client):
    response = client.patch("/api/opportunities/9999/verification", headers={"X-AutoEarn-Owner-Token": "test-owner-secret-0123456789-abcdef"}, json={
        "status": "verified"
    })
    assert response.status_code == 404


def test_opportunities_can_be_filtered_by_verification_status(client):
    item = opportunity(client)
    assert len(client.get("/api/opportunities?verification_status=pending").json()) == 1
    client.patch(f"/api/opportunities/{item['id']}/verification", headers={"X-AutoEarn-Owner-Token": "test-owner-secret-0123456789-abcdef"}, json={
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


def _prepare_verified_source(client):
    opp = opportunity(client)
    client.patch(f"/api/opportunities/{opp['id']}/status",
                 headers={"X-AutoEarn-Owner-Token": "test-owner-secret-0123456789-abcdef"},
                 params={"status": "eligible"})
    client.patch(f"/api/opportunities/{opp['id']}/verification",
                 headers={"X-AutoEarn-Owner-Token": "test-owner-secret-0123456789-abcdef"},
                 json={"status": "verified", "notes": "Terms and payout checked"})
    source = client.post("/api/sources", json={
        "name": "Verified source", "url": "https://example.com/source"
    }).json()
    client.patch(f"/api/sources/{source['id']}/review",
                 headers={"X-AutoEarn-Owner-Token": "test-owner-secret-0123456789-abcdef"},
                 json={"status": "approved", "notes": "Reviewed"})
    return opp, source


def test_supervision_api_requires_owner_token(client):
    assert client.get("/api/supervision/actions").status_code == 401


def test_supervised_action_requires_verified_opportunity_and_approved_source(client):
    opp = opportunity(client)
    source = client.post("/api/sources", json={
        "name": "Pending source", "url": "https://example.com/pending"
    }).json()
    response = client.post("/api/supervision/actions",
        headers={"X-AutoEarn-Owner-Token": "test-owner-secret-0123456789-abcdef"},
        json={"opportunity_id": opp["id"], "source_id": source["id"],
              "action": "submit_application", "description": "Submit after review"})
    assert response.status_code == 409


def test_supervision_api_persists_approval_and_audit(client):
    opp, source = _prepare_verified_source(client)
    headers = {"X-AutoEarn-Owner-Token": "test-owner-secret-0123456789-abcdef"}
    response = client.post("/api/supervision/actions", headers=headers, json={
        "opportunity_id": opp["id"], "source_id": source["id"],
        "action": "prepare_draft", "description": "Prepare application draft"})
    assert response.status_code == 201
    request_id = response.json()["request_id"]
    approved = client.post(f"/api/supervision/actions/{request_id}/approve", headers=headers)
    assert approved.status_code == 200
    completed = client.post(f"/api/supervision/actions/{request_id}/complete",
        headers=headers, json={"evidence": "Draft saved for owner review"})
    assert completed.status_code == 200
    audit = client.get(f"/api/supervision/actions/{request_id}/audit", headers=headers)
    assert [e["event_type"] for e in audit.json()] == [
        "requested", "approved", "marked_completed"]


def test_wrong_owner_token_is_rejected(client):
    response = client.get("/api/supervision/actions",
        headers={"X-AutoEarn-Owner-Token": "wrong"})
    assert response.status_code == 401


def test_owner_routes_fail_closed_when_secret_is_not_configured(client, monkeypatch):
    from app import main
    monkeypatch.setattr(main, "OWNER_TOKEN", "")
    response = client.get("/api/supervision/actions",
        headers={"X-AutoEarn-Owner-Token": "test-owner-secret-0123456789-abcdef"})
    assert response.status_code == 503


def test_source_review_cannot_be_changed_without_owner_auth(client):
    source = client.post("/api/sources", json={
        "name": "Unreviewed source", "url": "https://example.com/no-owner"
    }).json()
    response = client.patch(f"/api/sources/{source['id']}/review",
        json={"status": "approved", "notes": "unauthorized"})
    assert response.status_code == 401


def test_rss_discovery_requires_owner_token(client):
    response = client.post("/api/discovery/rss", json={
        "adapter_id": "feed-1", "display_name": "Public feed",
        "feed_url": "https://feeds.example.com/rss",
        "category": "surveys_microtasks",
        "allowed_domains": ["feeds.example.com", "tasks.example.com"]
    })
    assert response.status_code == 401


def test_rss_discovery_persists_only_pending_candidates_and_deduplicates(
    client, monkeypatch
):
    from types import SimpleNamespace
    from app import main

    class FakeRssAdapter:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def discover(self):
            return [
                SimpleNamespace(
                    title="Paid survey listing",
                    url="https://tasks.example.com/listing/1",
                    category="surveys_microtasks",
                    terms_url="",
                    summary="Public listing summary",
                    observed_at="2026-11-17T00:00:00+00:00",
                ),
                SimpleNamespace(
                    title="Duplicate listing",
                    url="https://tasks.example.com/listing/1",
                    category="surveys_microtasks",
                    terms_url="",
                    summary="Duplicate",
                    observed_at="2026-11-17T00:00:00+00:00",
                ),
            ]

    monkeypatch.setattr(main, "PublicRssAdapter", FakeRssAdapter)
    response = client.post("/api/discovery/rss",
        headers={"X-AutoEarn-Owner-Token": "test-owner-secret-0123456789-abcdef"},
        json={
            "adapter_id": "feed-1", "display_name": "Public feed",
            "feed_url": "https://feeds.example.com/rss",
            "category": "surveys_microtasks",
            "allowed_domains": ["feeds.example.com", "tasks.example.com"],
            "max_items": 10,
        })
    assert response.status_code == 200
    result = response.json()
    assert result["discovered_count"] == 2
    assert result["inserted_count"] == 1
    assert result["duplicate_count"] == 1
    assert result["review_required"] is True
    candidates = client.get("/api/sources?status=pending").json()
    assert len(candidates) == 1
    assert candidates[0]["name"] == "Paid survey listing"
    assert candidates[0]["category"] == "surveys_microtasks"
    assert candidates[0]["status"] == "pending"


def test_task_approval_and_reward_ledger_are_owner_only(client):
    opp = opportunity(client)
    task = client.post("/api/tasks",
        headers={"X-AutoEarn-Owner-Token": "test-owner-secret-0123456789-abcdef"},
        json={"opportunity_id": opp["id"], "description": "Manual work item"}).json()
    assert client.post(f"/api/tasks/{task['id']}/approve").status_code == 401
    assert client.post("/api/rewards", json={
        "opportunity_id": opp["id"], "amount": 999, "currency": "EUR",
        "status": "paid"
    }).status_code == 401
    assert client.get("/api/dashboard").status_code == 401


def test_owner_routes_disable_short_configured_tokens(client, monkeypatch):
    from app import main
    monkeypatch.setattr(main, "OWNER_TOKEN", "too-short")
    response = client.get("/api/supervision/actions",
        headers={"X-AutoEarn-Owner-Token": "too-short"})
    assert response.status_code == 503
