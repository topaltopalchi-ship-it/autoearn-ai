import pytest
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


def _ready_official_api_opportunity(client):
    headers = {"X-AutoEarn-Owner-Token": "test-owner-secret-0123456789-abcdef"}
    opportunity = client.post("/api/opportunities", headers=headers, json={
        "title": "Verified catalog task",
        "platform": "Example",
        "url": "https://example.com/catalog-task",
        "category": "freelancing_services",
        "eligible_countries": ["Germany"],
        "minimum_withdrawal_amount": 5,
        "withdrawal_currency": "EUR",
    })
    assert opportunity.status_code == 201
    opp = opportunity.json()
    source = client.post("/api/sources", headers=headers, json={
        "name": "Example official source",
        "url": "https://example.com/official-terms",
    })
    assert source.status_code == 201
    src = source.json()
    assert client.patch(
        f"/api/sources/{src['id']}/review", headers=headers,
        json={"status": "approved", "notes": "Terms checked"},
    ).status_code == 200
    assert client.patch(
        f"/api/opportunities/{opp['id']}/status", headers=headers,
        params={"status": "eligible"},
    ).status_code == 200
    assert client.patch(
        f"/api/opportunities/{opp['id']}/verification", headers=headers,
        json={"status": "verified", "notes": "Official terms verified"},
    ).status_code == 200
    return headers, opp, src


def _evaluate_official_api(client, headers, opp, src, ai_task_profile_marker=...):
    payload = {
        "source_id": src["id"],
        "country": "Germany",
        "execution_mode": "official_api",
        "reward_amount": 12,
        "reward_currency": "EUR",
        "estimated_cost": 2,
        "estimated_minutes": 30,
        "payment_probability": 95,
        "acceptance_probability": 95,
        "payout_reliability": 95,
        "payout_supported": True,
        "risk_score": 5,
        "evidence": ["Official terms and payout details reviewed"],
    }
    if ai_task_profile_marker is not ...:
        payload["ai_task_profile"] = ai_task_profile_marker
    return client.post(
        f"/api/opportunities/{opp['id']}/evaluate",
        headers=headers,
        json=payload,
    )


def test_official_api_readiness_requires_explicit_ai_task_profile(client):
    headers, opp, src = _ready_official_api_opportunity(client)
    response = _evaluate_official_api(client, headers, opp, src)
    assert response.status_code == 200
    result = response.json()
    assert result["evaluation"]["execution_allowed"] is False
    assert result["evaluation"]["ai_task_assessment"] is None
    assert result["execution_authorized"] is False
    assert any("AI task profile" in reason for reason in result["evaluation"]["risk_flags"])


def test_unknown_or_prohibited_ai_permission_blocks_official_api_readiness(client):
    headers, opp, src = _ready_official_api_opportunity(client)
    unknown = _evaluate_official_api(client, headers, opp, src, {
        "title": "Task with unclear rules",
        "ai_permission": "unknown",
    })
    assert unknown.status_code == 200
    assert unknown.json()["evaluation"]["execution_allowed"] is False
    assert unknown.json()["evaluation"]["ai_task_assessment"]["suitability"] == "manual_policy_review"

    prohibited = _evaluate_official_api(client, headers, opp, src, {
        "title": "Task prohibits AI",
        "ai_permission": "prohibited",
    })
    assert prohibited.status_code == 200
    assert prohibited.json()["evaluation"]["execution_allowed"] is False
    assert prohibited.json()["evaluation"]["ai_task_assessment"]["suitability"] == "blocked"


def test_human_only_task_blocks_official_api_readiness(client):
    headers, opp, src = _ready_official_api_opportunity(client)
    response = _evaluate_official_api(client, headers, opp, src, {
        "title": "Personal experience survey",
        "ai_permission": "allowed",
        "requires_personal_experience": True,
    })
    assert response.status_code == 200
    assert response.json()["evaluation"]["execution_allowed"] is False
    assert response.json()["evaluation"]["ai_task_assessment"]["suitability"] == "human_only"


def test_explicitly_permitted_verifiable_ai_draft_candidate_can_pass_readiness_only(client):
    headers, opp, src = _ready_official_api_opportunity(client)
    response = _evaluate_official_api(client, headers, opp, src, {
        "title": "Format public catalog data",
        "ai_permission": "allowed",
        "repetitive_information_processing": True,
        "output_is_objectively_verifiable": True,
        "human_signoff_required": True,
    })
    assert response.status_code == 200
    result = response.json()
    assert result["evaluation"]["ai_task_assessment"]["suitability"] == "ai_draft_candidate"
    assert result["evaluation"]["execution_allowed"] is True
    assert result["evaluation"]["execution_authorized"] is False
    assert result["execution_authorized"] is False
    assert "Human review and owner confirmation" in result["execution_note"]


def test_invalid_ai_task_profile_is_rejected(client):
    headers, opp, src = _ready_official_api_opportunity(client)
    response = _evaluate_official_api(client, headers, opp, src, {
        "title": "Invalid permission",
        "ai_permission": "maybe",
    })
    assert response.status_code == 422
