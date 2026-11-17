from datetime import datetime, timezone

from autoearn.ranking import rank_evaluations


def record(opportunity_id, title, currency, score, *, eligibility="eligible",
           stale=False, execution=False, flags=None):
    return {
        "opportunity_id": opportunity_id,
        "title": title,
        "execution_mode": "manual",
        "research": {
            "country_status": "verified",
            "payout_status": "verified",
            "ai_permission": "allowed",
            "api_status": "available",
            "checked_at": datetime.now(timezone.utc).isoformat(),
        },
        "evaluation": {
            "currency": currency,
            "ranking_score": score,
            "eligibility": eligibility,
            "evidence_stale": stale,
            "execution_allowed": execution,
            "risk_flags": flags or [],
        },
    }


def test_ranking_separates_currencies_and_orders_within_each_group():
    result = rank_evaluations([
        record(1, "Lower EUR", "EUR", 45),
        record(2, "Higher EUR", "eur", 82, execution=True),
        record(3, "USD item", "USD", 99),
    ])
    assert result["total"] == 3
    assert [group["currency"] for group in result["groups"]] == ["EUR", "USD"]
    eur = result["groups"][0]["items"]
    assert [item["title"] for item in eur] == ["Higher EUR", "Lower EUR"]
    assert eur[0]["rank_in_currency"] == 1
    assert result["groups"][1]["items"][0]["rank_in_currency"] == 1
    assert "not compared" in result["comparison_note"]


def test_ranking_tiers_do_not_treat_stale_or_ineligible_as_priority():
    result = rank_evaluations([
        record(1, "Fresh candidate", "EUR", 80),
        record(2, "Stale candidate", "EUR", 95, stale=True),
        record(3, "Excluded", "EUR", 99, eligibility="ineligible"),
    ])
    tiers = {item["title"]: item["priority_tier"]
             for item in result["groups"][0]["items"]}
    assert tiers["Fresh candidate"] == "priority_candidate"
    assert tiers["Stale candidate"] == "needs_review"
    assert tiers["Excluded"] == "low_priority"


def test_ranking_never_authorizes_execution():
    result = rank_evaluations([
        record(1, "Ready", "EUR", 90, execution=True),
    ])
    item = result["groups"][0]["items"][0]
    assert item["execution_allowed"] is True
    assert item["execution_authorized"] is False


def test_ai_fit_is_reported_separately_from_financial_priority():
    candidate = record(1, "AI task", "EUR", 85)
    candidate["evaluation"]["ai_task_assessment"] = {
        "suitability": "ai_draft_candidate", "score": 85,
    }
    result = rank_evaluations([candidate])
    item = result["groups"][0]["items"][0]
    assert item["priority_tier"] == "priority_candidate"
    assert item["ai_fit"] == "bounded_ai_draft_candidate"
    assert item["ai_suitability_score"] == 85
    assert item["execution_authorized"] is False


def test_ranking_blocks_unverified_country_payout_or_ai_permission():
    candidate = record(1, "Unverified task", "EUR", 99)
    candidate["research"]["payout_status"] = "unknown"
    result = rank_evaluations([candidate])
    item = result["groups"][0]["items"][0]
    assert item["priority_tier"] == "blocked_pending_research"
    assert item["research_complete"] is False
    assert item["research_status"]["payout"] == "unknown"
    assert item["execution_authorized"] is False


def test_official_api_mode_requires_separate_api_evidence():
    candidate = record(1, "API task", "EUR", 99)
    candidate["execution_mode"] = "official_api"
    candidate["research"]["api_status"] = "unknown"
    result = rank_evaluations([candidate])
    item = result["groups"][0]["items"][0]
    assert item["priority_tier"] == "blocked_api_unverified"
    assert item["research_complete"] is True
    assert item["api_research_ready"] is False
    assert item["execution_authorized"] is False


def test_ranking_blocks_missing_or_expired_research_timestamp():
    candidate = record(1, "Old evidence", "EUR", 99)
    candidate["research"]["checked_at"] = "2020-01-01T00:00:00+00:00"
    item = rank_evaluations([candidate])["groups"][0]["items"][0]
    assert item["priority_tier"] == "blocked_pending_research"
    assert item["research_fresh"] is False

    candidate["research"].pop("checked_at")
    item = rank_evaluations([candidate])["groups"][0]["items"][0]
    assert item["research_complete"] is False
    assert item["research_fresh"] is False


def test_ranking_does_not_accept_future_research_timestamp():
    candidate = record(1, "Future evidence", "EUR", 99)
    candidate["research"]["checked_at"] = "2999-01-01T00:00:00+00:00"
    item = rank_evaluations([candidate])["groups"][0]["items"][0]
    assert item["research_fresh"] is False
    assert item["priority_tier"] == "blocked_pending_research"



def test_financial_ranking_uses_verified_expected_net_hourly_within_currency():
    best = record(1, "Best expected return", "EUR", 70)
    best["evaluation"].update({
        "expected_net_hourly_estimate": 18.5,
        "payout_supported": True,
        "withdrawal_status": "immediately_reachable",
    })
    lower = record(2, "Lower expected return", "EUR", 95)
    lower["evaluation"].update({
        "expected_net_hourly_estimate": 7.25,
        "payout_supported": True,
        "withdrawal_status": "immediately_reachable",
    })
    unknown = record(3, "Unverified payout", "EUR", 100)
    unknown["evaluation"].update({
        "expected_net_hourly_estimate": 99,
        "payout_supported": None,
        "withdrawal_status": "immediately_reachable",
    })

    items = rank_evaluations([lower, unknown, best])["groups"][0]["items"]
    assert [item["title"] for item in items] == [
        "Best expected return", "Lower expected return", "Unverified payout",
    ]
    assert items[0]["financial_readiness"] == "ready"
    assert items[0]["expected_net_hourly_estimate"] == 18.5
    assert items[2]["financial_readiness"] == "needs_financial_verification"


def test_financial_ranking_accepts_accumulation_only_when_explicitly_confirmed():
    candidate = record(1, "Accumulation supported", "EUR", 60)
    candidate["evaluation"].update({
        "expected_net_hourly_estimate": 4.0,
        "payout_supported": True,
        "withdrawal_status": "requires_accumulation",
        "supports_balance_accumulation": True,
    })
    item = rank_evaluations([candidate])["groups"][0]["items"][0]
    assert item["financial_readiness"] == "ready"

    candidate["evaluation"]["supports_balance_accumulation"] = False
    item = rank_evaluations([candidate])["groups"][0]["items"][0]
    assert item["financial_readiness"] == "needs_financial_verification"


def test_financial_ranking_ignores_invalid_or_missing_hourly_values():
    candidate = record(1, "Missing hourly estimate", "EUR", 80)
    candidate["evaluation"].update({
        "payout_supported": True,
        "withdrawal_status": "immediately_reachable",
        "expected_net_hourly_estimate": float("nan"),
    })
    item = rank_evaluations([candidate])["groups"][0]["items"][0]
    assert item["expected_net_hourly_estimate"] is None
    assert item["financial_readiness"] == "needs_financial_verification"
