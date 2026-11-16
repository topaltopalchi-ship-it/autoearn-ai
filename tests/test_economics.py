import pytest

from autoearn.economics import EconomicsInput, evaluate_economics


def test_net_return_includes_costs_and_both_fee_types():
    result = evaluate_economics(EconomicsInput(
        gross_reward=100, estimated_hours=4, estimated_cost=10,
        fee_percent=5, flat_fee=2, currency="EUR", cost_currency="EUR",
        target_hourly_rate=15,
    ))
    assert result["percentage_fee"] == 5
    assert result["total_cost"] == 17
    assert result["estimated_net"] == 83
    assert result["estimated_net_per_hour"] == 20.75
    assert result["target_met"] is True
    assert result["minimum_gross_reward_for_target"] == 75.79
    assert result["verified"] is False


def test_zero_cost_has_no_infinite_roi():
    result = evaluate_economics(EconomicsInput(gross_reward=20, estimated_hours=2))
    assert result["estimated_net"] == 20
    assert result["roi_percent"] is None


def test_negative_net_is_reported_without_hiding_loss():
    result = evaluate_economics(EconomicsInput(
        gross_reward=5, estimated_hours=2, estimated_cost=8
    ))
    assert result["estimated_net"] == -3
    assert result["assessment"] == "negative"


@pytest.mark.parametrize("payload", [
    {"gross_reward": -1, "estimated_hours": 1},
    {"gross_reward": 1, "estimated_hours": 0},
    {"gross_reward": 1, "estimated_hours": 1, "fee_percent": 101},
    {"gross_reward": 1, "estimated_hours": 1, "currency": "EURO"},
])
def test_invalid_amounts_and_currency_are_rejected(payload):
    defaults = {"gross_reward": 1, "estimated_hours": 1}
    with pytest.raises(ValueError):
        evaluate_economics(EconomicsInput(**{**defaults, **payload}))


def test_mixed_currencies_are_never_silently_added():
    with pytest.raises(ValueError, match="must match"):
        evaluate_economics(EconomicsInput(
            gross_reward=20, estimated_hours=1, estimated_cost=5,
            currency="EUR", cost_currency="USD",
        ))


def test_full_percentage_fee_does_not_claim_break_even_reward():
    result = evaluate_economics(EconomicsInput(
        gross_reward=20, estimated_hours=1, fee_percent=100,
    ))
    assert result["minimum_gross_reward_for_target"] is None
