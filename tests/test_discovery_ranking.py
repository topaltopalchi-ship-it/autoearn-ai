from datetime import datetime, timezone, timedelta

from autoearn.discovery_ranking import prioritize_discovery_leads


def lead(**overrides):
    item = {
        "id": 1,
        "title": "Public task",
        "url": "https://example.com/task",
        "terms_url": "https://example.com/terms",
        "summary": "A sufficiently detailed public description " * 5,
        "feed_status": "approved",
        "total_checks": 10,
        "total_successes": 9,
        "last_seen_at": datetime.now(timezone.utc).isoformat(),
    }
    item.update(overrides)
    return item


def test_reliable_recent_lead_with_terms_is_research_first():
    result = prioritize_discovery_leads([lead()])
    item = result["items"][0]
    assert item["research_priority"] == "research_first"
    assert item["research_priority_score"] == 100
    assert item["feed_reliability_percent"] == 90


def test_missing_terms_and_unapproved_feed_are_low_signal():
    result = prioritize_discovery_leads([lead(
        terms_url="", summary="", feed_status="pending",
        total_checks=2, total_successes=2,
    )])
    item = result["items"][0]
    assert item["research_priority"] == "low_signal"
    assert item["feed_reliability_percent"] is None


def test_country_payout_and_ai_permissions_remain_unknown():
    result = prioritize_discovery_leads([lead()])
    item = result["items"][0]
    assert item["country_eligibility"] == "unknown"
    assert item["payout_availability"] == "unknown"
    assert item["ai_permission"] == "unknown"
    assert item["financial_evaluation_status"] == "not_evaluated"
    assert len(item["next_research_actions"]) == 5
    assert any("برداشت پول" in action for action in item["next_research_actions"])
    assert item["execution_authorized"] is False


def test_old_leads_are_not_awarded_freshness_points():
    result = prioritize_discovery_leads([lead(last_seen_at="2000-01-01T00:00:00+00:00")])
    assert result["items"][0]["research_priority_score"] == 90


def test_far_future_leads_are_not_awarded_freshness_points():
    result = prioritize_discovery_leads([lead(last_seen_at="2099-01-01T00:00:00+00:00")])
    assert result["items"][0]["research_priority_score"] == 90


def test_near_future_leads_are_not_awarded_freshness_points():
    future = (datetime.now(timezone.utc) + timedelta(hours=12)).isoformat()
    result = prioritize_discovery_leads([lead(last_seen_at=future)])
    assert result["items"][0]["research_priority_score"] == 90
    assert "تازگی فرصت تأیید نشده" in result["items"][0]["research_reasons"][-1]



def test_verified_country_and_payout_are_ranked_ahead_of_unresearched_leads():
    ready = lead(id=2, research_country_status="verified",
                 research_payout_status="verified", research_ai_permission="prohibited")
    unknown = lead(id=1)
    result = prioritize_discovery_leads([unknown, ready])
    first, second = result["items"]
    assert first["id"] == 2
    assert first["participation_readiness"] == "country_and_payout_verified"
    assert first["participation_readiness_score"] == 100
    assert first["country_eligibility"] == "eligible"
    assert first["payout_availability"] == "available"
    assert first["automation_policy"] == "manual_only"
    assert first["execution_authorized"] is False
    assert second["participation_readiness"] == "needs_country_or_payout_research"


def test_blocked_country_or_unavailable_payout_is_demoted():
    blocked_country = lead(id=3, research_country_status="blocked",
                           research_payout_status="verified")
    unavailable_payout = lead(id=2, research_country_status="verified",
                              research_payout_status="unavailable")
    unknown = lead(id=1)
    result = prioritize_discovery_leads([blocked_country, unavailable_payout, unknown])
    assert result["items"][0]["id"] == 1
    assert result["items"][1]["participation_readiness"] == "blocked_country"
    assert result["items"][2]["participation_readiness"] == "blocked_payout"
    assert all(item["execution_authorized"] is False for item in result["items"])
