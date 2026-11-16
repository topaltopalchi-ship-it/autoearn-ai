"""Explainable red-flag screening for online earning opportunities.

This is a checklist aid, not a fraud detector or legal/financial advice.
"""
from __future__ import annotations

from dataclasses import dataclass

@dataclass(frozen=True)
class RiskSignals:
    upfront_payment: bool = False
    deposit_or_top_up: bool = False
    guaranteed_high_returns: bool = False
    referral_required_to_withdraw: bool = False
    unclear_or_missing_terms: bool = False
    missing_payout_threshold: bool = False
    crypto_only_payout: bool = False
    requests_sensitive_data_early: bool = False
    asks_to_move_off_platform: bool = False
    unrealistic_time_pressure: bool = False

_WEIGHTS = {
    "upfront_payment": 20,
    "deposit_or_top_up": 25,
    "guaranteed_high_returns": 20,
    "referral_required_to_withdraw": 15,
    "unclear_or_missing_terms": 10,
    "missing_payout_threshold": 5,
    "crypto_only_payout": 5,
    "requests_sensitive_data_early": 15,
    "asks_to_move_off_platform": 10,
    "unrealistic_time_pressure": 10,
}
_LABELS = {
    "upfront_payment": "Requires an upfront payment",
    "deposit_or_top_up": "Requires a deposit or account top-up",
    "guaranteed_high_returns": "Promises unusually high or guaranteed returns",
    "referral_required_to_withdraw": "Requires referrals before withdrawal",
    "unclear_or_missing_terms": "Terms or eligibility are unclear",
    "missing_payout_threshold": "Minimum payout threshold is not stated",
    "crypto_only_payout": "Payout appears to be crypto-only",
    "requests_sensitive_data_early": "Requests sensitive personal or financial data early",
    "asks_to_move_off_platform": "Pushes communication or payment off-platform",
    "unrealistic_time_pressure": "Uses unusually urgent pressure tactics",
}

def assess_risk(signals: RiskSignals) -> dict:
    active = [name for name in _WEIGHTS if getattr(signals, name)]
    score = min(100, sum(_WEIGHTS[name] for name in active))
    level = "high" if score >= 50 else "medium" if score >= 25 else "low"
    return {
        "risk_score": score,
        "risk_level": level,
        "flags": [{"code": name, "weight": _WEIGHTS[name], "reason": _LABELS[name]} for name in active],
        "requires_human_review": bool(active),
        "verified": False,
        "disclaimer": "Heuristic checklist only. A low score does not prove legitimacy; verify official terms and the operator independently.",
    }
