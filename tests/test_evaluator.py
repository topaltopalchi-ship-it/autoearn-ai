from datetime import datetime, timezone

from autoearn.evaluator import OpportunityCandidate, evaluate_candidate


NOW = datetime(2026, 11, 17, 12, 0, tzinfo=timezone.utc)


def complete_candidate(**overrides):
    values = {
        "title": "Paid research task",
        "category": "surveys_microtasks",
        "source_status": "approved",
        "verification_status": "verified",
        "execution_mode": "official_api",
        "eligible_countries": ("Germany",),
        "observed_at": "2026-11-16T12:00:00+00:00",
        "reward_amount": 12.0,
        "reward_currency": "EUR",
        "estimated_cost": 2.0,
        "estimated_minutes": 30,
        "payment_probability": 90,
        "risk_score": 10,
        "evidence": ("Official terms page checked",),
    }
    values.update(overrides)
    return OpportunityCandidate(**values)


def test_explicit_country_eligibility_and_net_hourly_estimate():
    result = evaluate_candidate(complete_candidate(), "Germany", now=NOW)
    assert result["eligibility"] == "eligible"
    assert result["net_reward_estimate"] == 10.0
    assert result["net_hourly_estimate"] == 20.0
    assert result["execution_allowed"] is True


def test_country_not_listed_is_ineligible_when_allowlist_exists():
    result = evaluate_candidate(complete_candidate(), "France", now=NOW)
    assert result["eligibility"] == "ineligible"
    assert result["execution_allowed"] is False


def test_missing_country_data_remains_unknown():
    result = evaluate_candidate(
        complete_candidate(eligible_countries=(), excluded_countries=()),
        "Germany",
        now=NOW,
    )
    assert result["eligibility"] == "unknown"
    assert result["execution_allowed"] is False


def test_excluded_country_overrides_allowlist():
    result = evaluate_candidate(
        complete_candidate(excluded_countries=("Germany",)),
        "Germany",
        now=NOW,
    )
    assert result["eligibility"] == "ineligible"


def test_stale_evidence_blocks_execution():
    result = evaluate_candidate(
        complete_candidate(observed_at="2026-09-01T12:00:00+00:00"),
        "Germany",
        now=NOW,
    )
    assert result["evidence_stale"] is True
    assert result["execution_allowed"] is False
    assert "evidence is stale" in result["risk_flags"]


def test_manual_or_assisted_mode_never_auto_executes():
    for mode in ("manual", "assist"):
        result = evaluate_candidate(
            complete_candidate(execution_mode=mode),
            "Germany",
            now=NOW,
        )
        assert result["execution_allowed"] is False


def test_unapproved_or_unverified_source_never_auto_executes():
    for updates in (
        {"source_status": "pending"},
        {"verification_status": "pending"},
    ):
        result = evaluate_candidate(complete_candidate(**updates), "Germany", now=NOW)
        assert result["execution_allowed"] is False


def test_missing_evidence_and_payment_probability_reduce_confidence():
    result = evaluate_candidate(
        complete_candidate(evidence=(), payment_probability=None),
        "Germany",
        now=NOW,
    )
    assert result["confidence"] < 100
    assert result["execution_allowed"] is False
