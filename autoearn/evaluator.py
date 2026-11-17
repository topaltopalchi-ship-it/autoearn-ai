"""Deterministic eligibility and execution-safety evaluation.

This is a metadata evaluator, not an income predictor. Unknown evidence is
kept unknown and never silently promoted to eligibility or automation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from math import isfinite
from typing import Literal

Eligibility = Literal["eligible", "ineligible", "unknown"]
ExecutionMode = Literal["manual", "assist", "official_api"]
Category = Literal[
    "games_competitions",
    "surveys_microtasks",
    "freelancing_services",
    "ai_content_products",
    "other",
]


@dataclass(frozen=True)
class OpportunityCandidate:
    title: str
    category: Category
    source_status: Literal["pending", "approved", "rejected"] = "pending"
    verification_status: Literal["pending", "verified", "rejected"] = "pending"
    execution_mode: ExecutionMode = "manual"
    eligible_countries: tuple[str, ...] = ()
    excluded_countries: tuple[str, ...] = ()
    observed_at: str = ""
    reward_amount: float | None = None
    reward_currency: str = "EUR"
    estimated_cost: float = 0.0
    payout_fee_fixed: float = 0.0
    payout_fee_percent: float = 0.0
    conversion_fee_percent: float = 0.0
    minimum_withdrawal_amount: float | None = None
    estimated_minutes: int | None = None
    payment_probability: int | None = None
    payout_supported: bool | None = None
    risk_score: int | None = None
    evidence: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.title.strip():
            raise ValueError("title is required")
        if self.category not in ("games_competitions", "surveys_microtasks", "freelancing_services", "ai_content_products", "other"):
            raise ValueError("unsupported category")
        if self.execution_mode not in ("manual", "assist", "official_api"):
            raise ValueError("unsupported execution mode")
        if self.source_status not in ("pending", "approved", "rejected"):
            raise ValueError("unsupported source status")
        if self.verification_status not in ("pending", "verified", "rejected"):
            raise ValueError("unsupported verification status")
        monetary_fields = (
            "reward_amount", "estimated_cost", "payout_fee_fixed",
            "payout_fee_percent", "conversion_fee_percent",
            "minimum_withdrawal_amount",
        )
        for field_name in monetary_fields:
            value = getattr(self, field_name)
            if value is not None and not isfinite(value):
                raise ValueError(f"{field_name} must be a finite number")
        if self.reward_amount is not None and self.reward_amount < 0:
            raise ValueError("reward_amount cannot be negative")
        if self.estimated_cost < 0:
            raise ValueError("estimated_cost cannot be negative")
        for field_name in ("payout_fee_fixed", "payout_fee_percent", "conversion_fee_percent"):
            value = getattr(self, field_name)
            if value < 0 or (field_name.endswith("_percent") and value > 100):
                raise ValueError(f"{field_name} is outside its valid range")
        if self.minimum_withdrawal_amount is not None and self.minimum_withdrawal_amount < 0:
            raise ValueError("minimum_withdrawal_amount cannot be negative")
        if self.estimated_minutes is not None and self.estimated_minutes < 1:
            raise ValueError("estimated_minutes must be positive")
        if self.payment_probability is not None and not 0 <= self.payment_probability <= 100:
            raise ValueError("payment_probability must be from 0 to 100")
        if self.risk_score is not None and not 0 <= self.risk_score <= 100:
            raise ValueError("risk_score must be from 0 to 100")
        if not self.reward_currency.strip():
            raise ValueError("reward_currency is required")


def _country_key(value: str) -> str:
    return " ".join(value.casefold().split())


def evaluate_candidate(
    candidate: OpportunityCandidate,
    country: str,
    *,
    now: datetime | None = None,
    max_evidence_age_days: int = 30,
) -> dict[str, object]:
    """Return eligibility, confidence, flags, and a conservative ranking score."""
    if not country.strip():
        raise ValueError("country is required")
    if max_evidence_age_days < 0:
        raise ValueError("max_evidence_age_days cannot be negative")

    flags: list[str] = []
    country_key = _country_key(country)
    eligible = {_country_key(item) for item in candidate.eligible_countries}
    excluded = {_country_key(item) for item in candidate.excluded_countries}

    if country_key in excluded:
        eligibility: Eligibility = "ineligible"
        flags.append("country explicitly excluded")
    elif eligible:
        if country_key in eligible:
            eligibility = "eligible"
        else:
            eligibility = "ineligible"
            flags.append("country not in the explicit eligible-country list")
    else:
        eligibility = "unknown"
        flags.append("country eligibility is not documented")

    stale = False
    if not candidate.observed_at:
        stale = True
        flags.append("evidence observation time is missing")
    else:
        try:
            observed = datetime.fromisoformat(candidate.observed_at.replace("Z", "+00:00"))
            if observed.tzinfo is None:
                observed = observed.replace(tzinfo=timezone.utc)
            current = now or datetime.now(timezone.utc)
            if current.tzinfo is None:
                current = current.replace(tzinfo=timezone.utc)
            age_days = (current - observed).total_seconds() / 86400
            if age_days < 0:
                stale = True
                flags.append("evidence timestamp is in the future")
            elif age_days > max_evidence_age_days:
                stale = True
                flags.append("evidence is stale")
        except ValueError:
            stale = True
            flags.append("evidence timestamp is invalid")

    if candidate.source_status != "approved":
        flags.append("source has not been approved")
    if candidate.verification_status != "verified":
        flags.append("opportunity has not been verified")
    if not candidate.evidence:
        flags.append("no supporting evidence recorded")
    if candidate.payout_supported is not True:
        flags.append("payout support for this country is not verified")
    if candidate.payment_probability is None:
        flags.append("payment probability is unknown")
    elif candidate.payment_probability == 0:
        flags.append("estimated payment probability is zero")
    if candidate.estimated_minutes is None or candidate.estimated_minutes <= 0:
        flags.append("time estimate is missing or invalid")
    if candidate.reward_amount is None:
        flags.append("advertised reward is unknown")
    if candidate.risk_score is None:
        flags.append("risk assessment is missing")

    # Determine whether the estimated net reward clears the withdrawal
    # threshold before using that result in the execution gate.
    withdrawal_reachable = None
    if candidate.reward_amount is not None and candidate.minimum_withdrawal_amount is not None:
        gross_after_cost = max(0.0, candidate.reward_amount - candidate.estimated_cost)
        estimated_net = max(
            0.0,
            gross_after_cost
            - candidate.payout_fee_fixed
            - gross_after_cost * candidate.payout_fee_percent / 100
            - gross_after_cost * candidate.conversion_fee_percent / 100,
        )
        withdrawal_reachable = round(estimated_net, 2) >= candidate.minimum_withdrawal_amount

    execution_allowed = (
        eligibility == "eligible"
        and not stale
        and candidate.source_status == "approved"
        and candidate.verification_status == "verified"
        and bool(candidate.evidence)
        and candidate.execution_mode == "official_api"
        and candidate.reward_amount is not None
        and candidate.payout_supported is True
        and candidate.payment_probability is not None
        and candidate.payment_probability > 0
        and candidate.estimated_minutes is not None
        and candidate.risk_score is not None
        and withdrawal_reachable is True
    )
    if withdrawal_reachable is False:
        flags.append("estimated net reward is below the minimum withdrawal threshold")
    elif withdrawal_reachable is None:
        flags.append("minimum withdrawal threshold or net reward is unknown")
    if candidate.execution_mode != "official_api":
        flags.append("automatic execution is unavailable for this execution mode")

    confidence_inputs = sum((
        bool(candidate.eligible_countries),
        bool(candidate.observed_at) and not stale,
        candidate.source_status == "approved",
        candidate.verification_status == "verified",
        bool(candidate.evidence),
        candidate.payment_probability is not None,
        candidate.payout_supported is True,
        candidate.estimated_minutes is not None and candidate.estimated_minutes > 0,
        candidate.reward_amount is not None,
        candidate.risk_score is not None,
    ))
    confidence = round(confidence_inputs / 10 * 100)

    net_reward = None
    hourly_net = None
    expected_net_reward = None
    expected_hourly_net = None
    withdrawal_reachable = None
    if candidate.reward_amount is not None:
        gross_after_cost = max(0.0, candidate.reward_amount - candidate.estimated_cost)
        payout_fee = candidate.payout_fee_fixed + gross_after_cost * candidate.payout_fee_percent / 100
        conversion_fee = gross_after_cost * candidate.conversion_fee_percent / 100
        net_reward = round(max(0.0, gross_after_cost - payout_fee - conversion_fee), 2)
        if candidate.minimum_withdrawal_amount is not None:
            withdrawal_reachable = net_reward >= candidate.minimum_withdrawal_amount
        if candidate.payment_probability is not None:
            expected_net_reward = round(net_reward * candidate.payment_probability / 100, 2)
        if candidate.estimated_minutes and candidate.estimated_minutes > 0:
            hourly_net = round(net_reward / (candidate.estimated_minutes / 60), 2)
            if expected_net_reward is not None:
                expected_hourly_net = round(expected_net_reward / (candidate.estimated_minutes / 60), 2)

    score = 0
    if eligibility == "eligible":
        score += 30
    if candidate.source_status == "approved":
        score += 15
    if candidate.verification_status == "verified":
        score += 15
    if candidate.payment_probability is not None:
        score += round(max(0, min(100, candidate.payment_probability)) * 0.20)
    if expected_hourly_net is not None:
        score += max(0, min(20, round(expected_hourly_net)))
    if candidate.risk_score is not None:
        score -= round(max(0, min(100, candidate.risk_score)) * 0.10)
    if stale:
        score -= 20
    score = max(0, min(100, score))

    return {
        "eligibility": eligibility,
        "execution_allowed": execution_allowed,
        "confidence": confidence,
        "ranking_score": score,
        "net_reward_estimate": net_reward,
        "net_hourly_estimate": hourly_net,
        "expected_net_reward_estimate": expected_net_reward,
        "expected_net_hourly_estimate": expected_hourly_net,
        "payment_probability_percent": candidate.payment_probability,
        "payout_supported": candidate.payout_supported,
        "withdrawal_reachable_estimate": withdrawal_reachable,
        "payout_fee_estimate": round((candidate.payout_fee_fixed + (max(0.0, (candidate.reward_amount or 0) - candidate.estimated_cost) * candidate.payout_fee_percent / 100)), 2),
        "conversion_fee_estimate": round(max(0.0, (candidate.reward_amount or 0) - candidate.estimated_cost) * candidate.conversion_fee_percent / 100, 2),
        "currency": candidate.reward_currency.upper(),
        "evidence_stale": stale,
        "risk_flags": flags,
        "disclaimer": "Estimates are based on supplied evidence and do not guarantee participation, income, or payment.",
    }