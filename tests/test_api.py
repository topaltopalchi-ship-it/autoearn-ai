import pytest
import sqlite3
from fastapi.testclient import TestClient

from app.main import app


def owner_get(client, path):
    return client.get(path, headers={"X-AutoEarn-Owner-Token": "test-owner-secret-0123456789-abcdef"})


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
    response = client.get("/api/health")
    assert response.json()["status"] == "ok"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["permissions-policy"] == "camera=(), microphone=(), geolocation=()"
    csp = response.headers["content-security-policy"]
    assert "default-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp
    assert "object-src 'none'" in csp
    assert "script-src 'self'" in csp


def test_private_opportunity_and_source_lists_require_owner_token(client):
    assert client.get("/api/opportunities").status_code == 401
    assert client.get("/api/sources").status_code == 401


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

    listed = owner_get(client, "/api/sources?status=pending")
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
    assert owner_get(client, "/api/sources?status=pending").json() == []


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
    assert client.post("/api/opportunities", headers={"X-AutoEarn-Owner-Token": "test-owner-secret-0123456789-abcdef"}, json=payload).status_code == 201
    duplicate = client.post("/api/opportunities", headers={"X-AutoEarn-Owner-Token": "test-owner-secret-0123456789-abcdef"}, json=payload)
    assert duplicate.status_code == 409
    assert "already registered" in duplicate.json()["detail"]


def test_opportunity_duplicate_race_is_rejected_by_unique_index(client):
    from app import main

    # Simulate another request winning after the endpoint's preliminary SELECT
    # but immediately before its INSERT.
    with sqlite3.connect(main.DB_PATH) as db:
        db.execute("""
            CREATE TRIGGER simulate_concurrent_opportunity_insert
            BEFORE INSERT ON opportunities
            BEGIN
                INSERT INTO opportunities (title, platform, url, created_at)
                VALUES ('Concurrent winner', 'Example', NEW.url, '2026-01-01T00:00:00+00:00');
            END
        """)

    response = client.post(
        "/api/opportunities",
        headers={"X-AutoEarn-Owner-Token": "test-owner-secret-0123456789-abcdef"},
        json={"title": "Racing request", "platform": "Example", "url": "https://example.com/race"},
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "This opportunity URL is already registered."
    assert owner_get(client, "/api/opportunities").status_code == 200


def test_normalizes_duplicate_urls(client):
    payload = {
        "title": "Normalized URL", "platform": "Example Games",
        "url": "https://EXAMPLE.com/game/#tracking",
    }
    assert client.post("/api/opportunities", headers={"X-AutoEarn-Owner-Token": "test-owner-secret-0123456789-abcdef"}, json=payload).status_code == 201
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

    listed = owner_get(client, "/api/opportunities").json()
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
    assert len(owner_get(client, "/api/opportunities?verification_status=pending").json()) == 1
    client.patch(f"/api/opportunities/{item['id']}/verification", headers={"X-AutoEarn-Owner-Token": "test-owner-secret-0123456789-abcdef"}, json={
        "status": "verified", "notes": "Manually checked"
    })
    assert owner_get(client, "/api/opportunities?verification_status=pending").json() == []
    verified = owner_get(client, "/api/opportunities?verification_status=verified").json()
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
    source = client.post("/api/sources", headers={"X-AutoEarn-Owner-Token": "test-owner-secret-0123456789-abcdef"}, json={
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
    source = client.post("/api/sources", headers={"X-AutoEarn-Owner-Token": "test-owner-secret-0123456789-abcdef"}, json={
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
    source = client.post("/api/sources", headers={"X-AutoEarn-Owner-Token": "test-owner-secret-0123456789-abcdef"}, json={
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
                    track_key="microtasks",
                ),
                SimpleNamespace(
                    title="Duplicate listing",
                    url="https://tasks.example.com/listing/1",
                    category="surveys_microtasks",
                    terms_url="",
                    summary="Duplicate",
                    observed_at="2026-11-17T00:00:00+00:00",
                ),
                SimpleNamespace(
                    title="فرصت حل پازل روزانه",
                    url="https://tasks.example.com/listing/2",
                    category="games_competitions",
                    terms_url="",
                    summary="No reliable category clues",
                    observed_at="2026-11-17T00:00:00+00:00",
                    track_key="microtasks",
                ),
            ]

    monkeypatch.setattr(main, "PublicRssAdapter", FakeRssAdapter)
    response = client.post("/api/discovery/rss",
        headers={"X-AutoEarn-Owner-Token": "test-owner-secret-0123456789-abcdef"},
        json={
            "adapter_id": "feed-1", "display_name": "Public feed",
            "feed_url": "https://feeds.example.com/rss",            "category": "surveys_microtasks",
            "allowed_domains": ["feeds.example.com", "tasks.example.com"],
            "max_items": 10,
        })
    assert response.status_code == 200
    result = response.json()
    assert result["discovered_count"] == 3
    assert result["inserted_count"] == 2
    assert result["duplicate_count"] == 1
    assert result["review_required"] is True
    candidates = owner_get(client, "/api/discovery/leads?status=pending").json()
    assert len(candidates) == 2
    candidates_by_title = {candidate["title"]: candidate for candidate in candidates}
    assert set(candidates_by_title) == {
        "Paid survey listing",
        "فرصت حل پازل روزانه",
    }
    paid_survey = candidates_by_title["Paid survey listing"]
    assert paid_survey["category"] == "surveys_microtasks"
    assert paid_survey["status"] == "pending"
    assert paid_survey["track_key"] == "microtasks"
    assert paid_survey["track_review_status"] == "matched"
    puzzle = candidates_by_title["فرصت حل پازل روزانه"]
    # The supplied track_key is invalid for this category; the Persian
    # title is independently classified from its supported puzzle keywords.
    assert puzzle["track_key"] == "puzzle_solving"
    assert puzzle["track_review_status"] == "matched"


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


def test_opportunity_and_source_intake_are_owner_only(client):
    payload = {"title": "Blocked", "platform": "Example", "url": "https://example.com/blocked"}
    assert client.post("/api/opportunities", json=payload).status_code == 401
    assert client.post("/api/sources", json={
        "name": "Blocked source", "url": "https://example.com/blocked-source"
    }).status_code == 401


def test_opportunity_evaluation_uses_reviewed_source_country_and_evidence(client):
    headers = {"X-AutoEarn-Owner-Token": "test-owner-secret-0123456789-abcdef"}
    opp = client.post("/api/opportunities", headers=headers, json={
        "title": "Research task", "platform": "Example",
        "url": "https://example.com/task/7",
        "eligible_countries": ["Germany"],
        "excluded_countries": ["United States"],
        "minimum_withdrawal_amount": 5,
        "withdrawal_currency": "EUR",
    }).json()
    source = client.post("/api/sources", headers=headers, json={
        "name": "Example official source", "url": "https://example.com/source"
    }).json()
    client.patch(f"/api/sources/{source['id']}/review", headers=headers,
        json={"status": "approved", "notes": "Official source checked"})
    client.patch(f"/api/opportunities/{opp['id']}/status", headers=headers,
        params={"status": "eligible"})
    client.patch(f"/api/opportunities/{opp['id']}/verification", headers=headers,
        json={"status": "verified", "notes": "Country and payout terms checked"})

    payload = {
        "source_id": source["id"], "country": "Germany",
        "execution_mode": "official_api", "reward_amount": 12,
        "reward_currency": "EUR", "estimated_cost": 2,
        "estimated_minutes": 30, "payment_probability": 90,
        "risk_score": 10, "evidence": ["Official terms reviewed"],
    }
    result = client.post(f"/api/opportunities/{opp['id']}/evaluate",
        headers=headers, json=payload)
    assert result.status_code == 200
    evaluation = result.json()["evaluation"]
    assert evaluation["eligibility"] == "eligible"
    assert evaluation["net_reward_estimate"] == 10
    assert evaluation["net_hourly_estimate"] == 20
    # Official-API readiness must remain blocked until the task's AI
    # permission is explicitly reviewed and a suitability profile is supplied.
    assert evaluation["execution_allowed"] is False
    assert evaluation["ai_task_assessment"] is None
    assert any("AI task profile" in flag for flag in evaluation["risk_flags"])
    assert result.json()["execution_authorized"] is False
    assert "no external platform action is executed" in result.json()["execution_note"]


def test_opportunity_evaluation_applies_payout_fees_and_currency_safe_threshold(client):
    headers = {"X-AutoEarn-Owner-Token": "test-owner-secret-0123456789-abcdef"}
    opp = client.post("/api/opportunities", headers=headers, json={
        "title": "Payout fee task", "platform": "Example",
        "url": "https://example.com/payout-fees",
        "eligible_countries": ["Germany"],
        "minimum_withdrawal_amount": 8,
        "withdrawal_currency": "EUR",
    }).json()
    source = client.post("/api/sources", headers=headers, json={
        "name": "Example official source", "url": "https://example.com/source"
    }).json()
    client.patch(f"/api/sources/{source['id']}/review", headers=headers,
        json={"status": "approved"})
    client.patch(f"/api/opportunities/{opp['id']}/status", headers=headers,
        params={"status": "eligible"})
    client.patch(f"/api/opportunities/{opp['id']}/verification", headers=headers,
        json={"status": "verified"})

    result = client.post(f"/api/opportunities/{opp['id']}/evaluate",
        headers=headers, json={
            "source_id": source["id"], "country": "Germany",
            "execution_mode": "official_api", "reward_amount": 10,
            "reward_currency": "EUR", "estimated_cost": 1,
            "payout_fee_fixed": 0.5, "payout_fee_percent": 5,
            "conversion_fee_percent": 2, "estimated_minutes": 30,
            "payment_probability": 95, "risk_score": 5,
            "evidence": ["Official payout terms reviewed"],
        })
    assert result.status_code == 200
    evaluation = result.json()["evaluation"]
    assert evaluation["payout_fee_estimate"] == 0.95
    assert evaluation["conversion_fee_estimate"] == 0.18
    assert evaluation["net_reward_estimate"] == 7.87
    assert evaluation["withdrawal_reachable_estimate"] is False
    assert evaluation["execution_allowed"] is False
    assert evaluation["withdrawal_threshold_currency_mismatch"] is False

    mismatch = client.post(f"/api/opportunities/{opp['id']}/evaluate",
        headers=headers, json={
            "source_id": source["id"], "country": "Germany",
            "execution_mode": "official_api", "reward_amount": 10,
            "reward_currency": "USD", "estimated_minutes": 30,
            "payment_probability": 95, "risk_score": 5,
            "evidence": ["Official payout terms reviewed"],
        })
    assert mismatch.status_code == 200
    mismatch_evaluation = mismatch.json()["evaluation"]
    assert mismatch_evaluation["withdrawal_reachable_estimate"] is None
    assert mismatch_evaluation["withdrawal_threshold_currency_mismatch"] is True
    assert mismatch_evaluation["execution_allowed"] is False
    assert any("different currency" in flag
               for flag in mismatch_evaluation["risk_flags"])


def test_opportunity_evaluation_blocks_country_mismatch_and_unreviewed_status(client):
    headers = {"X-AutoEarn-Owner-Token": "test-owner-secret-0123456789-abcdef"}
    opp = client.post("/api/opportunities", headers=headers, json={
        "title": "Regional task", "platform": "Example",
        "url": "https://example.com/regional",
        "eligible_countries": ["Germany"],
    }).json()
    source = client.post("/api/sources", headers=headers, json={
        "name": "Example source", "url": "https://example.com/source"
    }).json()
    client.patch(f"/api/sources/{source['id']}/review", headers=headers,
        json={"status": "approved"})
    client.patch(f"/api/opportunities/{opp['id']}/verification", headers=headers,
        json={"status": "verified"})
    result = client.post(f"/api/opportunities/{opp['id']}/evaluate",
        headers=headers, json={
            "source_id": source["id"], "country": "France",
            "execution_mode": "official_api", "reward_amount": 5,
            "estimated_minutes": 10, "payment_probability": 95,
            "risk_score": 5, "evidence": ["Terms reviewed"],
        })
    assert result.status_code == 200
    assert result.json()["evaluation"]["eligibility"] == "ineligible"
    assert result.json()["evaluation"]["execution_allowed"] is False


def test_evaluation_rejects_source_from_different_host(client):
    headers = {"X-AutoEarn-Owner-Token": "test-owner-secret-0123456789-abcdef"}
    opp = client.post("/api/opportunities", headers=headers, json={
        "title": "Task", "platform": "Example", "url": "https://example.com/task"
    }).json()
    source = client.post("/api/sources", headers=headers, json={
        "name": "Different host", "url": "https://other.example/source"
    }).json()
    result = client.post(f"/api/opportunities/{opp['id']}/evaluate",
        headers=headers, json={"source_id": source["id"], "country": "Germany"})
    assert result.status_code == 409


def test_opportunity_evaluation_history_is_persisted_and_owner_only(client):
    headers = {"X-AutoEarn-Owner-Token": "test-owner-secret-0123456789-abcdef"}
    opp, source = _prepare_verified_source(client)
    payload = {
        "source_id": source["id"], "country": "Germany",
        "execution_mode": "manual", "reward_amount": 8,
        "reward_currency": "EUR", "estimated_cost": 1,
        "estimated_minutes": 20, "payment_probability": 80,
        "risk_score": 15, "evidence": ["Official payout terms reviewed"],
    }

    created = client.post(
        f"/api/opportunities/{opp['id']}/evaluate",
        headers=headers, json=payload,
    )
    assert created.status_code == 200
    body = created.json()
    assert body["evaluation_id"] > 0
    assert body["created_at"]

    history = client.get(
        f"/api/opportunities/{opp['id']}/evaluations", headers=headers,
    )
    assert history.status_code == 200
    entries = history.json()
    assert len(entries) == 1
    assert entries[0]["evaluation_id"] == body["evaluation_id"]
    assert entries[0]["source_id"] == source["id"]
    assert entries[0]["country"] == "Germany"
    assert entries[0]["request"]["reward_amount"] == 8
    assert entries[0]["evaluation"] == body["evaluation"]

    assert client.get(
        f"/api/opportunities/{opp['id']}/evaluations"
    ).status_code == 401


def test_evaluation_history_returns_404_for_unknown_opportunity(client):
    response = client.get(
        "/api/opportunities/9999/evaluations",
        headers={"X-AutoEarn-Owner-Token": "test-owner-secret-0123456789-abcdef"},
    )
    assert response.status_code == 404


def test_earnings_ledger_records_state_and_audit_history(client):
    headers = {"X-AutoEarn-Owner-Token": "test-owner-secret-0123456789-abcdef"}
    opp = opportunity(client)
    created = client.post("/api/earnings", headers=headers, json={
        "opportunity_id": opp["id"], "amount": 8.75, "currency": "eur",
        "state": "estimated", "reference": "weekly task",
        "evidence": "Official reward page"
    })
    assert created.status_code == 201
    item = created.json()
    assert item["currency"] == "EUR"
    assert item["state"] == "estimated"
    assert item["evidence"] == "Official reward page"

    moved = client.patch(f"/api/earnings/{item['id']}/state", headers=headers,
        json={"state": "earned", "note": "Work completed"})
    assert moved.status_code == 200
    assert moved.json()["state"] == "earned"

    pending = client.patch(f"/api/earnings/{item['id']}/state", headers=headers,
        json={"state": "pending", "note": "Awaiting platform confirmation"})
    assert pending.status_code == 200
    withdrawable = client.patch(f"/api/earnings/{item['id']}/state", headers=headers,
        json={"state": "withdrawable"})
    assert withdrawable.status_code == 200
    paid = client.patch(f"/api/earnings/{item['id']}/state", headers=headers,
        json={"state": "paid", "note": "Payment received"})
    assert paid.status_code == 200

    history = client.get(f"/api/earnings/{item['id']}/history", headers=headers)
    assert history.status_code == 200
    assert [event["to_state"] for event in history.json()] == [
        "estimated", "earned", "pending", "withdrawable", "paid"
    ]
    assert all(event["actor"] == "owner" for event in history.json())
    totals = client.get("/api/dashboard", headers=headers).json()["earnings_totals"]
    assert totals["EUR"]["paid"] == 8.75
    assert client.get("/api/earnings", headers=headers).json()[0]["id"] == item["id"]


def test_earnings_ledger_blocks_invalid_transitions_and_paid_mutation(client):
    headers = {"X-AutoEarn-Owner-Token": "test-owner-secret-0123456789-abcdef"}
    item = client.post("/api/earnings", headers=headers, json={
        "amount": 3, "currency": "EUR", "state": "estimated"
    }).json()
    invalid = client.patch(f"/api/earnings/{item['id']}/state", headers=headers,
        json={"state": "paid"})
    assert invalid.status_code == 409
    client.patch(f"/api/earnings/{item['id']}/state", headers=headers,
        json={"state": "earned"})
    client.patch(f"/api/earnings/{item['id']}/state", headers=headers,
        json={"state": "pending"})
    client.patch(f"/api/earnings/{item['id']}/state", headers=headers,
        json={"state": "withdrawable"})
    client.patch(f"/api/earnings/{item['id']}/state", headers=headers,
        json={"state": "paid"})
    terminal = client.patch(f"/api/earnings/{item['id']}/state", headers=headers,
        json={"state": "pending"})
    assert terminal.status_code == 409


def test_earnings_ledger_requires_owner_and_valid_opportunity(client):
    assert client.get("/api/earnings").status_code == 401
    assert client.post("/api/earnings", json={
        "amount": 2, "currency": "EUR"
    }).status_code == 401
    headers = {"X-AutoEarn-Owner-Token": "test-owner-secret-0123456789-abcdef"}
    missing = client.post("/api/earnings", headers=headers, json={
        "opportunity_id": 9999, "amount": 2, "currency": "EUR"
    })
    assert missing.status_code == 404


def test_rss_discovery_skips_opportunities_already_in_catalog(client, monkeypatch):
    from types import SimpleNamespace
    from app import main

    headers = {"X-AutoEarn-Owner-Token": "test-owner-secret-0123456789-abcdef"}
    existing = client.post("/api/opportunities", headers=headers, json={
        "title": "Already registered task", "platform": "Example",
        "url": "https://EXAMPLE.com/game/#utm_source=newsletter",
    })
    assert existing.status_code == 201

    class FakeRssAdapter:
        def __init__(self, **kwargs):
            pass

        def discover(self):
            return [SimpleNamespace(
                title="Same task from RSS",
                url="https://example.com/game/",
                category="surveys_microtasks",
                terms_url="",
                summary="Discovered from a second feed",
                observed_at="2026-11-17T00:00:00+00:00",
            )]

    monkeypatch.setattr(main, "PublicRssAdapter", FakeRssAdapter)
    response = client.post("/api/discovery/rss", headers=headers, json={
        "adapter_id": "feed-duplicate", "display_name": "Another public feed",
        "feed_url": "https://feeds.example.com/rss",
        "category": "surveys_microtasks",
        "allowed_domains": ["feeds.example.com", "example.com"],
        "max_items": 10,
    })
    assert response.status_code == 200
    result = response.json()
    assert result["inserted_count"] == 0
    assert result["duplicate_count"] == 1
    assert owner_get(client, "/api/sources").json() == []
    assert owner_get(client, "/api/discovery/leads").json() == []
def test_competition_agent_plans_and_dry_runs_without_external_submission(client):
    headers = {"X-AutoEarn-Owner-Token": "test-owner-secret-0123456789-abcdef"}
    payload = {
        "title": "Open logic contest",
        "url": "https://contest.example.com/event",
        "rules_url": "https://contest.example.com/rules",
        "task_type": "logic",
        "country": "Germany",
        "eligibility": "eligible",
        "terms_verified": True,
        "automated_agents_allowed": True,
        "official_api": True,
        "prize_amount": 100,
        "prize_currency": "EUR",
    }
    assert client.post("/api/competitions", json=payload).status_code == 401
    created = client.post("/api/competitions", headers=headers, json=payload)
    assert created.status_code == 201
    competition_id = created.json()["id"]

    planned = client.post(
        f"/api/competitions/{competition_id}/plan",
        headers=headers,
        json={"objective": "Solve the official logic puzzle"},
    )
    assert planned.status_code == 200
    assert planned.json()["plan"]["provider"] == "heuristic-baseline"
    assert planned.json()["plan"]["steps"]

    dry_run = client.post(f"/api/competitions/{competition_id}/dry-run", headers=headers)
    assert dry_run.status_code == 200
    assert dry_run.json()["external_submission"] is False
    assert dry_run.json()["status"] == "dry_run_only"
    assert "adapter" in " ".join(dry_run.json()["blockers"])

    history = client.get(f"/api/competitions/{competition_id}/history", headers=headers)
    assert history.status_code == 200
    assert len(history.json()) == 1
    assert history.json()[0]["mode"] == "dry_run"


def test_competition_submission_is_blocked_without_registered_official_adapter(client):
    headers = {"X-AutoEarn-Owner-Token": "test-owner-secret-0123456789-abcdef"}
    payload = {
        "title": "Open coding contest",
        "url": "https://contest.example.com/event",
        "rules_url": "https://contest.example.com/rules",
        "task_type": "coding",
        "country": "Germany",
        "eligibility": "eligible",
        "terms_verified": True,
        "automated_agents_allowed": True,
        "official_api": True,
    }
    created = client.post("/api/competitions", headers=headers, json=payload).json()
    response = client.post(
        f"/api/competitions/{created['id']}/submit",
        headers=headers,
        json={"adapter_id": "not-installed", "payload": {"answer": "42"}, "owner_confirmed": True},
    )
    assert response.status_code == 409
    assert "adapter" in response.json()["detail"].lower()


def test_competition_requires_https_rules_and_event_urls(client):
    headers = {"X-AutoEarn-Owner-Token": "test-owner-secret-0123456789-abcdef"}
    response = client.post("/api/competitions", headers=headers, json={
        "title": "Insecure contest", "url": "http://contest.example.com/event",
        "rules_url": "https://contest.example.com/rules", "country": "Germany",
    })
    assert response.status_code == 422




def test_owner_managed_discovery_feeds_require_review_and_batch_deduplicate(client, monkeypatch):
    from app import main
    from autoearn.adapters import DiscoveredLead

    headers = {"X-AutoEarn-Owner-Token": "test-owner-secret-0123456789-abcdef"}
    payload = {
        "name": "Trusted public feed",
        "feed_url": "https://feed.example/rss.xml",
        "category": "freelancing_services",
        "allowed_domains": ["feed.example"],
        "max_items": 12,
    }

    assert client.get("/api/discovery/feeds").status_code == 401
    created = client.post("/api/discovery/feeds", headers=headers, json=payload)
    assert created.status_code == 201
    feed = created.json()
    assert feed["status"] == "pending"
    assert feed["allowed_domains"] == ["feed.example"]

    duplicate = client.post("/api/discovery/feeds", headers=headers, json=payload)
    assert duplicate.status_code == 409

    # Pending feeds must never be fetched by a batch run.
    class NeverFetch:
        def __init__(self, **kwargs):
            raise AssertionError("pending feed must not be fetched")
    monkeypatch.setattr(main, "PublicRssAdapter", NeverFetch)
    skipped = client.post("/api/discovery/run", headers=headers)
    assert skipped.status_code == 200
    assert skipped.json()["approved_feed_count"] == 0

    approved = client.patch(
        f"/api/discovery/feeds/{feed['id']}/review", headers=headers,
        json={"status": "approved"},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"

    class FakeFeed:
        def __init__(self, **kwargs):
            self.feed_url = kwargs["feed_url"]
        def discover(self):
            return [
                DiscoveredLead(
                    title="Paid remote task", url="https://feed.example/tasks/one",
                    category="freelancing_services", source_name="Trusted public feed",
                    observed_at="2026-11-17T00:00:00+00:00",
                    summary="Terms need manual review",
                    evidence=("Public RSS feed: https://feed.example/rss.xml",),
                )
            ]
    monkeypatch.setattr(main, "PublicRssAdapter", FakeFeed)

    first = client.post("/api/discovery/run", headers=headers)
    assert first.status_code == 200
    result = first.json()
    assert result["approved_feed_count"] == 1
    assert result["successful_feed_count"] == 1
    assert result["inserted_count"] == 1
    assert result["review_required"] is True

    second = client.post("/api/discovery/run", headers=headers)
    assert second.status_code == 200
    assert second.json()["inserted_count"] == 0
    assert second.json()["duplicate_count"] == 1

    pending_leads = client.get("/api/discovery/leads?status=pending", headers=headers)
    assert pending_leads.status_code == 200
    assert any(item["url"] == "https://feed.example/tasks/one"
               for item in pending_leads.json())

    promoted = client.post(
        f"/api/discovery/leads/{pending_leads.json()[0]['id']}/promote",
        headers=headers,
    )
    assert promoted.status_code == 201
    assert promoted.json()["opportunity"]["status"] == "discovered"
    assert promoted.json()["opportunity"]["verification_status"] == "pending"

    promoted_again = client.post(
        f"/api/discovery/leads/{pending_leads.json()[0]['id']}/promote",
        headers=headers,
    )
    assert promoted_again.status_code == 201
    assert promoted_again.json()["already_promoted"] is True


def test_discovery_feed_rejects_non_https_host_mismatch_and_wildcards(client):
    headers = {"X-AutoEarn-Owner-Token": "test-owner-secret-0123456789-abcdef"}
    base = {
        "name": "Feed source", "category": "other",
        "allowed_domains": ["feed.example"],
    }
    http = client.post("/api/discovery/feeds", headers=headers, json={
        **base, "feed_url": "http://feed.example/rss.xml",
    })
    assert http.status_code == 422

    nonstandard_port = client.post("/api/discovery/feeds", headers=headers, json={
        **base, "feed_url": "https://feed.example:8443/rss.xml",
    })
    assert nonstandard_port.status_code == 422

    mismatch = client.post("/api/discovery/feeds", headers=headers, json={
        **base, "feed_url": "https://other.example/rss.xml",
    })
    assert mismatch.status_code == 422

    wildcard = client.post("/api/discovery/feeds", headers=headers, json={
        **base, "feed_url": "https://feed.example/rss.xml",
        "allowed_domains": ["*.example"],
    })
    assert wildcard.status_code == 422


def test_discovery_feed_review_missing_id_returns_404(client):
    headers = {"X-AutoEarn-Owner-Token": "test-owner-secret-0123456789-abcdef"}
    response = client.patch(
        "/api/discovery/feeds/9999/review", headers=headers,
        json={"status": "approved"},
    )
    assert response.status_code == 404


def test_discovery_lead_rejection_and_promotion_guards(client, monkeypatch):
    from app import main
    from autoearn.adapters import DiscoveredLead

    headers = {"X-AutoEarn-Owner-Token": "test-owner-secret-0123456789-abcdef"}
    class FakeFeed:
        def __init__(self, **kwargs): pass
        def discover(self):
            return [DiscoveredLead(
                title="Potential paid challenge", url="https://feed.example/challenge",
                category="games_competitions", source_name="Public feed",
                observed_at="2026-11-17T00:00:00+00:00",
                summary="Prize details not yet verified",
            )]
    monkeypatch.setattr(main, "PublicRssAdapter", FakeFeed)
    created = client.post("/api/discovery/rss", headers=headers, json={
        "adapter_id":"test-feed", "display_name":"Public feed",
        "feed_url":"https://feed.example/rss.xml",
        "category":"games_competitions", "allowed_domains":["feed.example"],
        "max_items":10,
    })
    assert created.status_code == 200
    leads = client.get("/api/discovery/leads", headers=headers).json()
    lead = next(item for item in leads if item["url"] == "https://feed.example/challenge")

    rejected = client.patch(
        f"/api/discovery/leads/{lead['id']}/review", headers=headers,
        json={"status":"rejected", "notes":"No verifiable payout terms"},
    )
    assert rejected.status_code == 200
    blocked = client.post(f"/api/discovery/leads/{lead['id']}/promote", headers=headers)
    assert blocked.status_code == 409

    missing = client.patch(
        "/api/discovery/leads/9999/review", headers=headers,
        json={"status":"rejected", "notes":""},
    )
    assert missing.status_code == 404



def test_discovery_scheduler_settings_are_owner_only_and_bounded(client):
    headers = {"X-AutoEarn-Owner-Token": "test-owner-secret-0123456789-abcdef"}
    assert client.get("/api/discovery/scheduler").status_code == 401
    assert client.patch("/api/discovery/scheduler", json={
        "enabled": True, "interval_minutes": 180,
    }).status_code == 401

    initial = client.get("/api/discovery/scheduler", headers=headers)
    assert initial.status_code == 200
    assert initial.json()["enabled"] is True
    assert initial.json()["interval_minutes"] == 360

    invalid = client.patch("/api/discovery/scheduler", headers=headers, json={
        "enabled": True, "interval_minutes": 15,
    })
    assert invalid.status_code == 422

    updated = client.patch("/api/discovery/scheduler", headers=headers, json={
        "enabled": False, "interval_minutes": 180,
    })
    assert updated.status_code == 200
    assert updated.json()["enabled"] is False
    assert updated.json()["interval_minutes"] == 180


def test_scheduled_discovery_runs_due_batch_once_and_persists_result(client, monkeypatch):
    from app import main

    calls = []
    def fake_batch():
        calls.append(True)
        return {
            "checked_at": "2026-11-17T12:00:00+00:00",
            "approved_feed_count": 2,
            "successful_feed_count": 2,
            "inserted_count": 3,
            "duplicate_count": 1,
            "feeds": [],
            "review_required": True,
            "note": "All discovered items remain pending for owner review.",
        }

    monkeypatch.setattr(main, "_run_approved_discovery_batch", fake_batch)
    assert main._run_discovery_if_due() is True
    assert main._run_discovery_if_due() is False
    assert len(calls) == 1

    headers = {"X-AutoEarn-Owner-Token": "test-owner-secret-0123456789-abcdef"}
    state = client.get("/api/discovery/scheduler", headers=headers)
    assert state.status_code == 200
    assert state.json()["last_result"]["inserted_count"] == 3
    assert state.json()["last_completed_at"]
    assert state.json()["lease_until"] is None


def test_discovery_health_is_owner_only_and_reports_feed_state(client):
    from app import main
    assert client.get("/api/discovery/health").status_code == 401
    headers = {"X-AutoEarn-Owner-Token": "test-owner-secret-0123456789-abcdef"}
    created = client.post("/api/discovery/feeds", headers=headers, json={
        "name": "Health feed", "feed_url": "https://feed.example.com/rss",
        "category": "other", "allowed_domains": ["feed.example.com"],
        "max_items": 10,
    })
    assert created.status_code == 201
    feed_id = created.json()["id"]
    pending = client.get("/api/discovery/health", headers=headers).json()
    assert pending["counts"]["pending_review"] == 1
    assert pending["feeds"][0]["health"] == "not_active"
    approved = client.patch(f"/api/discovery/feeds/{feed_id}/review", headers=headers,
                            json={"status": "approved"})
    assert approved.status_code == 200
    with main.connect() as db:
        db.execute("UPDATE discovery_feeds SET last_checked_at = ?, last_success_at = ?, consecutive_failures = 0, total_checks = 4, total_successes = 3, last_error = '' WHERE id = ?",
                   (main.now(), main.now(), feed_id))
    healthy = client.get("/api/discovery/health", headers=headers).json()
    assert healthy["counts"]["healthy"] == 1
    assert healthy["feeds"][0]["last_success_at"] is not None
    assert healthy["feeds"][0]["total_checks"] == 4
    assert healthy["feeds"][0]["total_successes"] == 3
    assert healthy["feeds"][0]["reliability_percent"] == 75.0
    assert healthy["feeds"][0]["reliability_sample"] == "limited"
    with main.connect() as db:
        db.execute("UPDATE discovery_feeds SET last_checked_at = ?, consecutive_failures = 2, total_checks = 5, total_successes = 3, last_error = 'timeout' WHERE id = ?",
                   (main.now(), feed_id))
    failed = client.get("/api/discovery/health", headers=headers).json()
    assert failed["counts"]["error"] == 1
    assert failed["feeds"][0]["consecutive_failures"] == 2
    assert failed["feeds"][0]["last_error"] == "timeout"
    assert failed["feeds"][0]["reliability_percent"] == 60.0


def test_ranked_opportunities_uses_latest_country_evaluation_and_separates_currencies(client):
    from app import main

    headers = {"X-AutoEarn-Owner-Token": "test-owner-secret-0123456789-abcdef"}
    assert client.get("/api/opportunities/ranked?country=Germany").status_code == 401
    first, source = _prepare_verified_source(client)
    second_response = client.post("/api/opportunities", headers=headers, json={
        "title": "Second reward task", "platform": "Example",
        "url": "https://example.com/game-second",
        "eligible_countries": ["Germany"],
    })
    assert second_response.status_code == 201
    second = second_response.json()
    client.patch(f"/api/opportunities/{second['id']}/status", headers=headers,
                 params={"status": "eligible"})
    client.patch(f"/api/opportunities/{second['id']}/verification", headers=headers,
                 json={"status": "verified", "notes": "Reviewed"})

    def evaluate(opp_id, currency, reward):
        return client.post(f"/api/opportunities/{opp_id}/evaluate", headers=headers, json={
            "source_id": source["id"], "country": "Germany",
            "execution_mode": "manual", "reward_amount": reward,
            "reward_currency": currency, "estimated_minutes": 30,
            "payment_probability": 80, "risk_score": 20,
            "evidence": ["Official terms reviewed"],
        })

    older = evaluate(first["id"], "EUR", 8)
    latest = evaluate(first["id"], "EUR", 12)
    other_currency = evaluate(second["id"], "USD", 15)
    assert older.status_code == latest.status_code == other_currency.status_code == 200

    # Link one promoted discovery lead to the first opportunity and attach
    # country-specific evidence; the second opportunity remains unresearched.
    with main.connect() as db:
        lead_id = db.execute(
            """INSERT INTO discovery_leads
               (source_name, title, url, category, summary, terms_url, observed_at,
                status, created_at, last_seen_at, opportunity_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'converted', ?, ?, ?)""",
            ("Official source", "First task", "https://example.com/game",
             "other", "Listing", "https://example.com/terms", main.now(),
             main.now(), main.now(), first["id"]),
        ).lastrowid
    evidence = client.put(
        f"/api/discovery/leads/{lead_id}/research",
        headers=headers,
        json={
            "country": "Germany",
            "country_status": "verified",
            "country_evidence_url": "https://official.example/country",
            "payout_status": "verified",
            "payout_evidence_url": "https://official.example/payout",
            "ai_permission": "allowed",
            "ai_evidence_url": "https://official.example/ai-policy",
            "api_status": "available",
            "api_evidence_url": "https://official.example/api",
        },
    )
    assert evidence.status_code == 200

    ranked = client.get("/api/opportunities/ranked?country=Germany", headers=headers)
    assert ranked.status_code == 200
    body = ranked.json()
    assert body["total"] == 2
    assert [group["currency"] for group in body["groups"]] == ["EUR", "USD"]
    eur_item = body["groups"][0]["items"][0]
    assert eur_item["opportunity_id"] == first["id"]
    assert eur_item["evaluation_id"] == latest.json()["evaluation_id"]
    assert eur_item["evaluation"]["net_reward_estimate"] == 12
    assert eur_item["research_complete"] is True
    usd_item = body["groups"][1]["items"][0]
    assert usd_item["priority_tier"] == "blocked_pending_research"
    assert usd_item["research_status"]["country"] == "unknown"
    assert all(item["execution_authorized"] is False
               for group in body["groups"] for item in group["items"])
    assert "Different currencies" in body["comparison_note"] or "different currencies" in body["comparison_note"].lower()


def test_prioritized_discovery_endpoint_is_owner_only_and_marks_unknowns(client):
    from app import main

    assert client.get("/api/discovery/leads/prioritized").status_code == 401
    with main.connect() as db:
        feed = db.execute(
            """INSERT INTO discovery_feeds
               (name, feed_url, category, allowed_domains, max_items, status, created_at,
                total_checks, total_successes)
               VALUES (?, ?, ?, ?, ?, 'approved', ?, 10, 9)""",
            ("Trusted feed", "https://example.com/feed.xml", "surveys_microtasks",
             '["example.com"]', 30, main.now()),
        ).lastrowid
        db.execute(
            """INSERT INTO discovery_leads
               (source_feed_id, source_name, title, url, category, summary,
                terms_url, observed_at, status, created_at, last_seen_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)""",
            (feed, "Trusted feed", "Example task", "https://example.com/task",
             "surveys_microtasks", "Detailed public task description " * 8,
             "https://example.com/terms", main.now(), main.now(), main.now()),
        )

    response = owner_get(client, "/api/discovery/leads/prioritized")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    item = body["items"][0]
    assert item["research_priority"] == "research_first"
    assert item["feed_reliability_percent"] == 90
    assert item["financial_evaluation_status"] == "not_evaluated"
    assert item["country_eligibility"] == "unknown"
    assert item["payout_availability"] == "unknown"
    assert item["ai_permission"] == "unknown"
    assert item["research_country"] == "Iran"
    assert item["research_status"] == {
        "country": "unknown", "payout": "unknown",
        "ai_permission": "unknown", "api": "unknown",
    }
    assert item["execution_authorized"] is False

    with main.connect() as db:
        db.execute(
            """INSERT INTO discovery_research
               (lead_id, country, country_status, payout_status, ai_permission,
                api_status, updated_at)
               VALUES (?, 'Iran', 'verified', 'unavailable', 'prohibited',
                       'available', ?)""",
            (item["id"], main.now()),
        )
    reviewed = owner_get(
        client, "/api/discovery/leads/prioritized?country=Iran"
    ).json()["items"][0]
    assert reviewed["research_status"] == {
        "country": "verified", "payout": "unavailable",
        "ai_permission": "prohibited", "api": "available",
    }
    assert reviewed["country_eligibility"] == "eligible"
    assert reviewed["payout_availability"] == "unavailable"
    assert reviewed["participation_readiness"] == "blocked_payout"
    assert reviewed["participation_readiness_score"] == 0
    assert reviewed["automation_policy"] == "manual_only"
    assert reviewed["execution_authorized"] is False

    other_country = owner_get(
        client, "/api/discovery/leads/prioritized?country=Germany"
    ).json()["items"][0]
    assert other_country["research_status"]["country"] == "unknown"


def test_discovery_research_requires_official_https_evidence_and_is_owner_only(client):
    from app import main

    with main.connect() as db:
        lead_id = db.execute(
            """INSERT INTO discovery_leads
               (source_name, title, url, category, summary, terms_url, observed_at,
                status, created_at, last_seen_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)""",
            ("Research source", "Research task", "https://research.example/task",
             "freelancing_services", "Public listing", "https://research.example/terms",
             main.now(), main.now(), main.now()),
        ).lastrowid

    path = f"/api/discovery/leads/{lead_id}/research"
    assert client.get(path, params={"country": "Azerbaijan"}).status_code == 401
    assert client.put(path, json={"country": "Azerbaijan"}).status_code == 401
    headers = {"X-AutoEarn-Owner-Token": "test-owner-secret-0123456789-abcdef"}

    initial = client.get(path, headers=headers, params={"country": "Azerbaijan"})
    assert initial.status_code == 200
    assert initial.json()["country_status"] == "unknown"
    assert initial.json()["payout_status"] == "unknown"
    assert initial.json()["ai_permission"] == "unknown"
    assert initial.json()["api_status"] == "unknown"
    assert initial.json()["execution_authorized"] is False

    missing_evidence = client.put(path, headers=headers, json={
        "country": "Azerbaijan", "country_status": "verified",
    })
    assert missing_evidence.status_code == 422

    insecure_evidence = client.put(path, headers=headers, json={
        "country": "Azerbaijan", "country_status": "verified",
        "country_evidence_url": "http://official.example/eligibility",
    })
    assert insecure_evidence.status_code == 422

    for unsafe_url in (
        "https://localhost/eligibility",
        "https://service.local/internal",
        "https://127.0.0.1/eligibility",
        "https://10.0.0.8/payouts",
        "https://user:pass@official.example/terms",
    ):
        rejected = client.put(path, headers=headers, json={
            "country": "Azerbaijan", "country_status": "verified",
            "country_evidence_url": unsafe_url,
        })
        assert rejected.status_code == 422, unsafe_url

    payload = {
        "country": "Azerbaijan",
        "country_status": "verified",
        "country_evidence_url": "https://official.example/eligibility",
        "payout_status": "verified",
        "payout_evidence_url": "https://official.example/payouts",
        "ai_permission": "allowed",
        "ai_evidence_url": "https://official.example/terms",
        "api_status": "available",
        "api_evidence_url": "https://official.example/developers",
        "notes": "Official pages reviewed manually.",
    }
    saved = client.put(path, headers=headers, json=payload)
    assert saved.status_code == 200
    body = saved.json()
    assert body["country_status"] == "verified"
    assert body["payout_status"] == "verified"
    assert body["ai_permission"] == "allowed"
    assert body["api_status"] == "available"
    assert body["execution_authorized"] is False
    assert body["evidence_validation_note"] == (
        "Only HTTPS URL shape and public-host checks are performed; "
        "page authenticity and contents require owner review."
    )

    loaded = client.get(path, headers=headers, params={"country": "Azerbaijan"})
    assert loaded.status_code == 200
    assert loaded.json()["country_evidence_url"] == payload["country_evidence_url"]
    assert loaded.json()["notes"] == payload["notes"]



def test_opportunity_evaluation_requires_explicit_country_payout_support_for_readiness(client):
    headers = {"X-AutoEarn-Owner-Token": "test-owner-secret-0123456789-abcdef"}
    opp = opportunity(client)
    source_response = client.post("/api/sources", headers=headers, json={
        "name": "Example review", "url": "https://example.com/review",
        "terms_url": "https://example.com/terms",
    })
    assert source_response.status_code == 201
    source = source_response.json()
    client.patch(f"/api/sources/{source['id']}/review", headers=headers,
                 json={"status": "approved", "notes": "Reviewed"})
    client.patch(f"/api/opportunities/{opp['id']}/verification", headers=headers,
                 json={"status": "verified", "notes": "Reviewed"})
    payload = {
        "source_id": source["id"], "country": "Iran", "execution_mode": "official_api",
        "reward_amount": 12, "reward_currency": "EUR", "estimated_minutes": 30,
        "payment_probability": 90, "acceptance_probability": 80,
        "payout_reliability": 75, "risk_score": 5,
        "evidence": ["Official terms reviewed"],
        "ai_task_profile": {"title": "Data task", "ai_permission": "allowed",
                            "repetitive_information_processing": True,
                            "output_is_objectively_verifiable": True},
    }
    unknown = client.post(f"/api/opportunities/{opp['id']}/evaluate", headers=headers, json=payload)
    assert unknown.status_code == 200
    assert unknown.json()["evaluation"]["execution_allowed"] is False
    assert unknown.json()["evaluation"]["payout_supported"] is None
    payload["payout_supported"] = False
    blocked = client.post(f"/api/opportunities/{opp['id']}/evaluate", headers=headers, json=payload)
    assert blocked.status_code == 200
    assert blocked.json()["evaluation"]["execution_allowed"] is False
    payload["payout_supported"] = True
    verified = client.post(f"/api/opportunities/{opp['id']}/evaluate", headers=headers, json=payload)
    assert verified.status_code == 200
    assert verified.json()["evaluation"]["payout_supported"] is True
    assert verified.json()["evaluation"]["combined_success_probability_percent"] == 54
    assert verified.json()["evaluation"]["expected_net_reward_estimate"] == 6.48
    assert verified.json()["execution_authorized"] is False


def test_discovery_track_assignment_is_persistent_and_category_scoped(client):
    from app import main

    headers = {"X-AutoEarn-Owner-Token": "test-owner-secret-0123456789-abcdef"}
    assert client.get("/api/discovery/tracks?category=games_competitions").status_code == 401
    assert client.put("/api/discovery/leads/1/track", headers=headers,
                      json={"track_key": "puzzle_solving"}).status_code == 404

    with main.connect() as db:
        lead_id = db.execute(
            """INSERT INTO discovery_leads
               (source_name, title, url, category, observed_at, created_at, last_seen_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            ("Public feed", "Logic puzzle", "https://example.com/logic",
             "games_competitions", main.now(), main.now(), main.now()),
        ).lastrowid

    options = owner_get(client, "/api/discovery/tracks?category=games_competitions")
    assert options.status_code == 200
    assert "puzzle_solving" in [item["key"] for item in options.json()]
    puzzle = next(item for item in options.json() if item["key"] == "puzzle_solving")
    assert puzzle["execution_guidance"] == "assist_if_permitted"
    assert "اجازه" in puzzle["description"]

    assigned = client.put(
        f"/api/discovery/leads/{lead_id}/track", headers=headers,
        json={"track_key": "puzzle_solving"},
    )
    assert assigned.status_code == 200
    assert assigned.json()["track_key"] == "puzzle_solving"
    assert assigned.json()["track_review_status"] == "matched"
    assert assigned.json()["execution_authorized"] is False

    mismatch = client.put(
        f"/api/discovery/leads/{lead_id}/track", headers=headers,
        json={"track_key": "microtasks"},
    )
    assert mismatch.status_code == 422

    unassigned = client.put(
        f"/api/discovery/leads/{lead_id}/track", headers=headers,
        json={"track_key": ""},
    )
    assert unassigned.status_code == 200
    assert unassigned.json()["track_key"] == ""
    assert unassigned.json()["track_review_status"] == "needs_review"

    persisted = client.get("/api/discovery/leads", headers=headers).json()
    saved = next(item for item in persisted if item["id"] == lead_id)
    assert saved["track_review_status"] == "needs_review"


def test_discovery_lease_fencing_prevents_stale_worker_releasing_new_lease(client):
    from app import main
    from datetime import datetime, timedelta, timezone

    first_token = main._acquire_discovery_lease(force=True)
    assert first_token
    with main.connect() as db:
        expired = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        db.execute(
            "UPDATE discovery_scheduler SET lease_until = ? WHERE id = 1",
            (expired,),
        )

    second_token = main._acquire_discovery_lease(force=True)
    assert second_token
    assert second_token != first_token

    # The old worker may finish late, but it must not clear or overwrite the
    # lease now owned by the newer worker.
    assert main._finish_discovery_lease(first_token, error="stale worker") is False
    state = client.get(
        "/api/discovery/scheduler",
        headers={"X-AutoEarn-Owner-Token": "test-owner-secret-0123456789-abcdef"},
    ).json()
    assert state["lease_until"] is not None

    assert main._finish_discovery_lease(second_token, result={"inserted_count": 7}) is True
    state = client.get(
        "/api/discovery/scheduler",
        headers={"X-AutoEarn-Owner-Token": "test-owner-secret-0123456789-abcdef"},
    ).json()
    assert state["lease_until"] is None
    assert state["last_result"]["inserted_count"] == 7
    assert state["last_error"] == ""



def test_discovery_scheduler_migrates_existing_database_with_legacy_lease_schema(tmp_path, monkeypatch):
    import sqlite3
    from app import main

    legacy_db = tmp_path / "legacy.db"
    with sqlite3.connect(legacy_db) as db:
        db.execute(
            """CREATE TABLE discovery_scheduler (
                id INTEGER PRIMARY KEY CHECK(id = 1),
                enabled INTEGER NOT NULL DEFAULT 1,
                interval_minutes INTEGER NOT NULL DEFAULT 360,
                lease_until TEXT,
                last_started_at TEXT,
                last_completed_at TEXT,
                last_result_json TEXT NOT NULL DEFAULT '{}',
                last_error TEXT NOT NULL DEFAULT ''
            )"""
        )
        db.execute(
            "INSERT INTO discovery_scheduler (id, enabled, interval_minutes) VALUES (1, 1, 360)"
        )

    monkeypatch.setattr(main, "DB_PATH", legacy_db)
    main.init_db()
    with main.connect() as db:
        columns = {row["name"] for row in db.execute("PRAGMA table_info(discovery_scheduler)")}
        state = db.execute("SELECT lease_token FROM discovery_scheduler WHERE id = 1").fetchone()
    assert "lease_token" in columns
    assert state["lease_token"] == ""


def test_discovery_worker_does_not_report_success_after_lease_loss(client, monkeypatch):
    from app import main

    monkeypatch.setattr(main, "_acquire_discovery_lease", lambda force=False: "old-worker-token")
    monkeypatch.setattr(main, "_run_approved_discovery_batch", lambda: {"inserted_count": 2})
    monkeypatch.setattr(main, "_finish_discovery_lease", lambda *args, **kwargs: False)

    assert main._run_discovery_once(force=True) is None


def test_discovery_batch_continues_after_one_feed_failure(client, monkeypatch):
    from app import main
    from autoearn.adapters import DiscoveredLead

    headers = {"X-AutoEarn-Owner-Token": "test-owner-secret-0123456789-abcdef"}
    payloads = [
        {"name": "Broken feed", "feed_url": "https://broken.example/rss",
         "category": "other", "allowed_domains": ["broken.example"], "max_items": 10},
        {"name": "Healthy feed", "feed_url": "https://healthy.example/rss",
         "category": "freelancing_services", "allowed_domains": ["healthy.example"], "max_items": 10},
    ]
    feed_ids = []
    for payload in payloads:
        created = client.post("/api/discovery/feeds", headers=headers, json=payload)
        assert created.status_code == 201
        feed_id = created.json()["id"]
        feed_ids.append(feed_id)
        approved = client.patch(
            f"/api/discovery/feeds/{feed_id}/review", headers=headers,
            json={"status": "approved"},
        )
        assert approved.status_code == 200

    class MixedFeed:
        def __init__(self, **kwargs):
            self.feed_url = kwargs["feed_url"]

        def discover(self):
            if "broken.example" in self.feed_url:
                raise ValueError("simulated malformed feed")
            return [DiscoveredLead(
                title="Verified-format task", url="https://healthy.example/task/1",
                category="freelancing_services", source_name="Healthy feed",
                observed_at="2026-11-17T00:00:00+00:00",
                summary="Country and payout still require review",
            )]

    monkeypatch.setattr(main, "PublicRssAdapter", MixedFeed)
    response = client.post("/api/discovery/run", headers=headers)
    assert response.status_code == 200
    result = response.json()
    assert result["approved_feed_count"] == 2
    assert result["successful_feed_count"] == 1
    assert result["inserted_count"] == 1
    by_id = {item["feed_id"]: item for item in result["feeds"]}
    assert by_id[feed_ids[0]]["status"] == "error"
    assert "simulated malformed feed" in by_id[feed_ids[0]]["error"]
    assert by_id[feed_ids[1]]["status"] == "ok"

    with main.connect() as db:
        broken = db.execute(
            "SELECT consecutive_failures, total_checks FROM discovery_feeds WHERE id = ?",
            (feed_ids[0],),
        ).fetchone()
        healthy = db.execute(
            "SELECT consecutive_failures, total_checks, total_successes FROM discovery_feeds WHERE id = ?",
            (feed_ids[1],),
        ).fetchone()
    assert tuple(broken) == (1, 1)
    assert tuple(healthy) == (0, 1, 1)


def test_dashboard_defaults_to_users_iran_residence_country(client):
    response = client.get("/")
    assert response.status_code == 200
    page = response.text
    assert 'id="rank-country" value="Iran"' in page
    assert page.count('name="country" value="Iran"') == 2
    assert "Azerbaijan" not in page


def test_execution_control_is_owner_only_and_paused_by_default(client):
    assert client.get("/api/execution-control").status_code == 401
    initial = owner_get(client, "/api/execution-control")
    assert initial.status_code == 200
    assert initial.json()["paused"] is True
    assert client.patch("/api/execution-control", json={"paused": False}).status_code == 401

    headers = {"X-AutoEarn-Owner-Token": "test-owner-secret-0123456789-abcdef"}
    updated = client.patch(
        "/api/execution-control",
        headers=headers,
        json={"paused": False, "reason": "Owner explicitly enabled reviewed execution"},
    )
    assert updated.status_code == 200
    assert updated.json()["paused"] is False
    assert updated.json()["updated_by"] == "owner"
    assert owner_get(client, "/api/execution-control").json()["paused"] is False


def test_global_emergency_pause_blocks_registered_competition_submission(client, monkeypatch):
    from types import SimpleNamespace
    from app import main

    class RegisteredButNeverCalled:
        def get_manifest(self, adapter_id):
            return SimpleNamespace(allowed_actions=("submit_entry",))

        def submit(self, *args, **kwargs):
            raise AssertionError("emergency pause must block before adapter submission")

    monkeypatch.setattr(main, "competition_adapters", RegisteredButNeverCalled())
    headers = {"X-AutoEarn-Owner-Token": "test-owner-secret-0123456789-abcdef"}
    created = client.post("/api/competitions", headers=headers, json={
        "title": "Open coding contest",
        "url": "https://contest.example.com/event",
        "rules_url": "https://contest.example.com/rules",
        "task_type": "coding",
        "country": "Germany",
        "eligibility": "eligible",
        "terms_verified": True,
        "automated_agents_allowed": True,
        "official_api": True,
    })
    assert created.status_code == 201
    response = client.post(
        f"/api/competitions/{created.json()['id']}/submit",
        headers=headers,
        json={"adapter_id": "reviewed-adapter", "payload": {"answer": "42"}, "owner_confirmed": True},
    )
    assert response.status_code == 423
    assert "emergency pause" in response.json()["detail"].lower()


def test_emergency_pause_update_waits_for_inflight_submission_gate(client, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    from types import SimpleNamespace
    from app import main

    headers = {"X-AutoEarn-Owner-Token": "test-owner-secret-0123456789-abcdef"}
    created = client.post("/api/competitions", headers=headers, json={
        "title": "Open coding contest",
        "url": "https://contest.example.com/event",
        "rules_url": "https://contest.example.com/rules",
        "task_type": "coding",
        "country": "Germany",
        "eligibility": "eligible",
        "terms_verified": True,
        "automated_agents_allowed": True,
        "official_api": True,
    })
    assert created.status_code == 201
    competition_id = created.json()["id"]
    assert client.patch("/api/execution-control", headers=headers,
                        json={"paused": False, "reason": "test"}).status_code == 200

    adapter_entered = Event()
    release_adapter = Event()
    pause_request_reached_update = Event()

    class BlockingAdapter:
        def get_manifest(self, adapter_id):
            return SimpleNamespace(allowed_actions=("submit_entry",))

        def submit(self, *args, **kwargs):
            adapter_entered.set()
            assert release_adapter.wait(timeout=5)
            return SimpleNamespace(status="submitted", external_entry_id="entry-1", evidence={})

    monkeypatch.setattr(main, "competition_adapters", BlockingAdapter())
    original_now = main.now

    def observed_now():
        pause_request_reached_update.set()
        return original_now()

    with ThreadPoolExecutor(max_workers=2) as pool:
        submission = pool.submit(
            client.post,
            f"/api/competitions/{competition_id}/submit",
            headers=headers,
            json={"adapter_id": "reviewed-adapter", "payload": {"answer": "42"},
                  "owner_confirmed": True},
        )
        assert adapter_entered.wait(timeout=5)
        monkeypatch.setattr(main, "now", observed_now)
        pause = pool.submit(
            client.patch, "/api/execution-control", headers=headers,
            json={"paused": True, "reason": "Emergency stop"},
        )
        assert pause_request_reached_update.wait(timeout=5)
        assert not pause.done()
        release_adapter.set()
        assert submission.result(timeout=5).status_code == 200
        assert pause.result(timeout=5).status_code == 200

    blocked = client.post(
        f"/api/competitions/{competition_id}/submit",
        headers=headers,
        json={"adapter_id": "reviewed-adapter", "payload": {"answer": "42"},
              "owner_confirmed": True},
    )
    assert blocked.status_code == 423


def test_concurrent_earning_state_transitions_are_serialized(client, monkeypatch):
    import time
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event, Lock
    from app import main

    headers = {"X-AutoEarn-Owner-Token": "test-owner-secret-0123456789-abcdef"}
    item = client.post("/api/earnings", headers=headers, json={
        "amount": 12.5, "currency": "EUR", "state": "estimated"
    }).json()
    for state in ("earned", "pending", "withdrawable"):
        response = client.patch(
            f"/api/earnings/{item['id']}/state", headers=headers,
            json={"state": state},
        )
        assert response.status_code == 200

    first_transition_entered = Event()
    release_first_transition = Event()
    second_request_started = Event()
    call_lock = Lock()
    calls = 0
    original_now = main.now

    def controlled_now():
        nonlocal calls
        with call_lock:
            calls += 1
            call_number = calls
        if call_number == 1:
            first_transition_entered.set()
            assert release_first_transition.wait(timeout=5)
        return original_now()

    monkeypatch.setattr(main, "now", controlled_now)

    def move_to_pending():
        return client.patch(
            f"/api/earnings/{item['id']}/state", headers=headers,
            json={"state": "pending", "note": "first concurrent decision"},
        )

    def move_to_paid():
        second_request_started.set()
        return client.patch(
            f"/api/earnings/{item['id']}/state", headers=headers,
            json={"state": "paid", "note": "conflicting concurrent decision"},
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(move_to_pending)
        assert first_transition_entered.wait(timeout=5)
        second = pool.submit(move_to_paid)
        assert second_request_started.wait(timeout=5)
        time.sleep(0.1)
        assert not second.done()
        release_first_transition.set()
        assert first.result(timeout=5).status_code == 200
        assert second.result(timeout=5).status_code == 409

    final = client.get(f"/api/earnings", headers=headers).json()
    record = next(row for row in final if row["id"] == item["id"])
    assert record["state"] == "pending"
    history = client.get(
        f"/api/earnings/{item['id']}/history", headers=headers
    ).json()
    assert [event["to_state"] for event in history][-2:] == ["withdrawable", "pending"]


def test_all_api_routes_except_health_require_owner_authentication():
    from app import main

    public_api_paths = {"/api/health"}
    protected = [
        route for route in main.app.routes
        if getattr(route, "path", "").startswith("/api/")
        and route.path not in public_api_paths
        and hasattr(route, "dependant")
    ]
    assert protected
    for route in protected:
        dependency_calls = {dependency.call for dependency in route.dependant.dependencies}
        assert main.require_owner in dependency_calls, (
            f"{route.path} is missing owner authentication"
        )


def test_earning_evidence_upload_is_private_validated_and_downloadable(client, tmp_path, monkeypatch):
    import hashlib
    from app import main

    monkeypatch.setattr(main, "EVIDENCE_DIR", tmp_path / "private-evidence")
    headers = {"X-AutoEarn-Owner-Token": "test-owner-secret-0123456789-abcdef"}
    earning = client.post(
        "/api/earnings", headers=headers,
        json={"amount": 14.5, "currency": "EUR", "state": "earned"},
    ).json()
    payload = b"%PDF-1.4\n% owner receipt evidence\n"
    uploaded = client.post(
        f"/api/earnings/{earning['id']}/evidence",
        headers=headers,
        files={"upload": ("receipt.pdf", payload, "application/pdf")},
    )
    assert uploaded.status_code == 201
    metadata = uploaded.json()
    assert metadata["ledger_id"] == earning["id"]
    assert metadata["media_type"] == "application/pdf"
    assert metadata["size_bytes"] == len(payload)
    assert metadata["sha256"] == hashlib.sha256(payload).hexdigest()
    assert list((tmp_path / "private-evidence").iterdir())

    listed = client.get(
        f"/api/earnings/{earning['id']}/evidence", headers=headers
    )
    assert listed.status_code == 200
    assert listed.json()[0]["id"] == metadata["id"]

    downloaded = client.get(
        f"/api/earnings/{earning['id']}/evidence/{metadata['id']}",
        headers=headers,
    )
    assert downloaded.status_code == 200
    assert downloaded.content == payload
    assert downloaded.headers["cache-control"] == "no-store"
    assert client.get(
        f"/api/earnings/{earning['id']}/evidence/{metadata['id']}"
    ).status_code == 401


def test_earning_evidence_rejects_unsupported_and_mismatched_files(client):
    headers = {"X-AutoEarn-Owner-Token": "test-owner-secret-0123456789-abcdef"}
    earning = client.post(
        "/api/earnings", headers=headers,
        json={"amount": 1, "currency": "EUR"},
    ).json()
    unsupported = client.post(
        f"/api/earnings/{earning['id']}/evidence", headers=headers,
        files={"upload": ("script.html", b"<script>alert(1)</script>", "text/html")},
    )
    assert unsupported.status_code == 415
    mismatch = client.post(
        f"/api/earnings/{earning['id']}/evidence", headers=headers,
        files={"upload": ("fake.pdf", b"not a pdf", "application/pdf")},
    )
    assert mismatch.status_code == 415


def test_earning_evidence_rejects_files_over_five_mib(client):
    headers = {"X-AutoEarn-Owner-Token": "test-owner-secret-0123456789-abcdef"}
    earning = client.post(
        "/api/earnings", headers=headers,
        json={"amount": 1, "currency": "EUR"},
    ).json()
    oversized = b"%PDF-" + (b"x" * (5 * 1024 * 1024))
    response = client.post(
        f"/api/earnings/{earning['id']}/evidence", headers=headers,
        files={"upload": ("large.pdf", oversized, "application/pdf")},
    )
    assert response.status_code == 413


def test_approved_feed_has_persistent_sixty_second_cooldown(client, monkeypatch):
    from app import main

    headers = {"X-AutoEarn-Owner-Token": "test-owner-secret-0123456789-abcdef"}
    created = client.post("/api/discovery/feeds", headers=headers, json={
        "name": "Cooldown feed", "feed_url": "https://cooldown.example/rss",
        "category": "other", "allowed_domains": ["cooldown.example"],
        "max_items": 10,
    })
    assert created.status_code == 201
    feed_id = created.json()["id"]
    approved = client.patch(
        f"/api/discovery/feeds/{feed_id}/review", headers=headers,
        json={"status": "approved"},
    )
    assert approved.status_code == 200
    with main.connect() as db:
        db.execute(
            "UPDATE discovery_feeds SET last_checked_at = ? WHERE id = ?",
            (main.now(), feed_id),
        )

    class NeverFetch:
        def __init__(self, **kwargs):
            raise AssertionError("feed inside cooldown must not be fetched")

    monkeypatch.setattr(main, "PublicRssAdapter", NeverFetch)
    result = client.post("/api/discovery/run", headers=headers)
    assert result.status_code == 200
    feed_result = next(item for item in result.json()["feeds"] if item["feed_id"] == feed_id)
    assert feed_result["status"] == "rate_limited"
    assert 1 <= feed_result["retry_after_seconds"] <= 60
    assert result.json()["inserted_count"] == 0
