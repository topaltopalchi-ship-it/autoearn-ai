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
    assert client.get("/api/health").json()["status"] == "ok"


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
            "feed_url": "https://feeds.example.com/rss",            "category": "surveys_microtasks",
            "allowed_domains": ["feeds.example.com", "tasks.example.com"],
            "max_items": 10,
        })
    assert response.status_code == 200
    result = response.json()
    assert result["discovered_count"] == 2
    assert result["inserted_count"] == 1
    assert result["duplicate_count"] == 1
    assert result["review_required"] is True
    candidates = owner_get(client, "/api/sources?status=pending").json()
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
    assert evaluation["execution_allowed"] is True
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