from datetime import datetime, timezone

import pytest

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
        "minimum_withdrawal_amount": 5.0,
        "estimated_cost": 2.0,
        "estimated_minutes": 30,
        "payment_probability": 90,
        "acceptance_probability": 100,
        "payout_reliability": 100,
        "payout_supported": True,
        "payout_route_configured": True,
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


def test_probability_weighted_expected_net_earnings():
    result = evaluate_candidate(
        complete_candidate(payment_probability=50),
        "Germany",
        now=NOW,
    )
    assert result["net_reward_estimate"] == 10.0
    assert result["net_hourly_estimate"] == 20.0
    assert result["expected_net_reward_estimate"] == 5.0
    assert result["expected_net_hourly_estimate"] == 10.0
    assert result["payment_probability_percent"] == 50


def test_unknown_payment_probability_keeps_expected_earnings_unknown():
    result = evaluate_candidate(
        complete_candidate(payment_probability=None),
        "Germany",
        now=NOW,
    )
    assert result["net_reward_estimate"] == 10.0
    assert result["expected_net_reward_estimate"] is None
    assert result["expected_net_hourly_estimate"] is None


def test_zero_payment_probability_blocks_execution():
    result = evaluate_candidate(
        complete_candidate(payment_probability=0),
        "Germany",
        now=NOW,
    )
    assert result["expected_net_reward_estimate"] == 0.0
    assert result["execution_allowed"] is False
    assert "estimated payment probability is zero" in result["risk_flags"]


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


def test_any_future_evidence_timestamp_blocks_execution():
    from datetime import timedelta

    future = (NOW + timedelta(hours=12)).isoformat()
    result = evaluate_candidate(
        complete_candidate(observed_at=future),
        "Germany",
        now=NOW,
    )
    assert result["evidence_stale"] is True
    assert result["execution_allowed"] is False
    assert "evidence timestamp is in the future" in result["risk_flags"]


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


def test_incomplete_payout_evidence_blocks_automatic_execution():
    result = evaluate_candidate(
        complete_candidate(payment_probability=None),
        "Germany",
        now=NOW,
    )
    assert result["execution_allowed"] is False
    assert "payment probability is unknown" in result["risk_flags"]


def test_candidate_rejects_invalid_probability_and_negative_cost():
    with pytest.raises(ValueError, match="payment_probability"):
        complete_candidate(payment_probability=101)
    with pytest.raises(ValueError, match="acceptance_probability"):
        complete_candidate(acceptance_probability=101)
    with pytest.raises(ValueError, match="payout_reliability"):
        complete_candidate(payout_reliability=-1)
    with pytest.raises(ValueError, match="estimated_cost"):
        complete_candidate(estimated_cost=-1)


@pytest.mark.parametrize(
    "field,value",
    [
        ("reward_amount", float("nan")),
        ("reward_amount", float("inf")),
        ("estimated_cost", float("nan")),
        ("payout_fee_fixed", float("inf")),
        ("payout_fee_percent", float("nan")),
        ("conversion_fee_percent", float("inf")),
        ("minimum_withdrawal_amount", float("nan")),
    ],
)
def test_non_finite_money_values_are_rejected(field, value):
    with pytest.raises(ValueError, match=field):
        complete_candidate(**{field: value})


def test_unknown_execution_mode_is_rejected():
    with pytest.raises(ValueError, match="execution mode"):
        complete_candidate(execution_mode="browser_bot")


def test_net_reward_deducts_payout_and_conversion_fees():
    result = evaluate_candidate(
        complete_candidate(payout_fee_fixed=0.50, payout_fee_percent=5,
                           conversion_fee_percent=2),
        "Germany", now=NOW,
    )
    # 12 reward - 2 cost = 10; fees: 0.50 + 0.50 + 0.20.
    assert result["net_reward_estimate"] == 8.8
    assert result["payout_fee_estimate"] == 1.0
    assert result["conversion_fee_estimate"] == 0.2


def test_minimum_withdrawal_threshold_blocks_execution_below_threshold():
    result = evaluate_candidate(
        complete_candidate(minimum_withdrawal_amount=10),
        "Germany", now=NOW,
    )
    assert result["net_reward_estimate"] == 10.0
    assert result["withdrawal_reachable_estimate"] is True
    assert result["execution_allowed"] is True

    blocked = evaluate_candidate(
        complete_candidate(minimum_withdrawal_amount=10.01),
        "Germany", now=NOW,
    )
    assert blocked["withdrawal_reachable_estimate"] is False
    assert blocked["execution_allowed"] is False
    assert "estimated net reward is below the minimum withdrawal threshold" in blocked["risk_flags"]


def test_invalid_payout_fee_is_rejected():
    import pytest
    with pytest.raises(ValueError, match="payout_fee_percent"):
        complete_candidate(payout_fee_percent=101)


def test_unknown_withdrawal_threshold_blocks_automatic_execution():
    result = evaluate_candidate(
        complete_candidate(minimum_withdrawal_amount=None),
        "Germany", now=NOW,
    )
    assert result["withdrawal_reachable_estimate"] is None
    assert result["execution_allowed"] is False
    assert "minimum withdrawal threshold or net reward is unknown" in result["risk_flags"]


@pytest.mark.parametrize("payout_supported", [None, False])
def test_unknown_or_unsupported_country_payout_blocks_execution(payout_supported):
    result = evaluate_candidate(
        complete_candidate(payout_supported=payout_supported), "Germany", now=NOW
    )
    assert result["execution_allowed"] is False
    assert result["payout_supported"] is payout_supported
    assert "payout support for this country is not verified" in result["risk_flags"]


def test_explicitly_verified_country_payout_can_pass_payout_gate():
    result = evaluate_candidate(complete_candidate(payout_supported=True), "Germany", now=NOW)
    assert result["payout_supported"] is True
    assert result["execution_allowed"] is True



def test_expected_earnings_combine_acceptance_payment_and_payout_reliability():
    result = evaluate_candidate(
        complete_candidate(
            acceptance_probability=80,
            payment_probability=90,
            payout_reliability=75,
        ),
        "Germany", now=NOW,
    )
    # Combined success probability: 80% × 90% × 75% = 54%.
    assert result["combined_success_probability_percent"] == 54
    assert result["expected_net_reward_estimate"] == 5.4
    assert result["expected_net_hourly_estimate"] == 10.8


def test_expected_earnings_remain_unknown_if_any_probability_input_is_missing():
    result = evaluate_candidate(
        complete_candidate(payout_reliability=None),
        "Germany", now=NOW,
    )
    assert result["combined_success_probability_percent"] is None
    assert result["expected_net_reward_estimate"] is None
    assert result["expected_net_hourly_estimate"] is None
    assert result["execution_allowed"] is False
    assert "payout-channel reliability is unknown" in result["risk_flags"]



def test_below_threshold_can_be_accumulated_when_platform_confirms_it():
    result = evaluate_candidate(
        complete_candidate(
            minimum_withdrawal_amount=25,
            supports_balance_accumulation=True,
        ),
        "Germany", now=NOW,
    )
    assert result["withdrawal_reachable_estimate"] is False
    assert result["withdrawal_status"] == "requires_accumulation"
    assert result["execution_allowed"] is True
    assert "single-task reward is below the withdrawal threshold; balance accumulation is required" in result["risk_flags"]


def test_currency_mismatch_never_compares_reward_withdrawal_threshold():
    result = evaluate_candidate(
        complete_candidate(
            reward_currency="USD",
            minimum_withdrawal_amount=5,
            minimum_withdrawal_currency="USDT",
            supports_balance_accumulation=True,
        ),
        "Germany", now=NOW,
    )
    assert result["withdrawal_reachable_estimate"] is None
    assert result["withdrawal_status"] == "currency_mismatch"
    assert result["execution_allowed"] is False
    assert any("currency differs" in flag for flag in result["risk_flags"])


def test_below_threshold_without_accumulation_support_remains_blocked():
    result = evaluate_candidate(
        complete_candidate(
            minimum_withdrawal_amount=25,
            supports_balance_accumulation=None,
        ),
        "Germany", now=NOW,
    )
    assert result["withdrawal_status"] == "below_minimum_withdrawal"
    assert result["execution_allowed"] is False


@pytest.mark.parametrize("route_configured", [None, False])
def test_unconfigured_owner_payout_route_blocks_execution(route_configured):
    result = evaluate_candidate(
        complete_candidate(payout_route_configured=route_configured), "Germany", now=NOW
    )
    assert result["execution_allowed"] is False
    assert result["payout_route_configured"] is route_configured
    assert "the owner has not configured a usable payout method" in result["risk_flags"]


def test_explicitly_configured_owner_payout_route_can_pass_route_gate():
    result = evaluate_candidate(
        complete_candidate(payout_route_configured=True), "Germany", now=NOW
    )
    assert result["payout_route_configured"] is True
    assert result["execution_allowed"] is True
