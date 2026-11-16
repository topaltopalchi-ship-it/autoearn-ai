from autoearn.risk import RiskSignals, assess_risk


def test_no_flags_is_low_but_not_verified():
    result = assess_risk(RiskSignals())
    assert result["risk_score"] == 0
    assert result["risk_level"] == "low"
    assert result["verified"] is False


def test_deposit_and_upfront_payment_trigger_high_risk():
    result = assess_risk(RiskSignals(upfront_payment=True, deposit_or_top_up=True))
    assert result["risk_score"] == 45
    assert result["risk_level"] == "medium"
    assert result["requires_human_review"] is True
    assert len(result["flags"]) == 2


def test_multiple_red_flags_are_capped_at_100():
    result = assess_risk(RiskSignals(
        upfront_payment=True, deposit_or_top_up=True,
        guaranteed_high_returns=True, referral_required_to_withdraw=True,
        requests_sensitive_data_early=True, asks_to_move_off_platform=True,
    ))
    assert result["risk_score"] == 100
    assert result["risk_level"] == "high"
