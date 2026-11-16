"""Deterministic net-return estimates from owner-supplied opportunity data.

No external API calls, currency conversion, or earnings guarantees are involved.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import re


@dataclass(frozen=True)
class EconomicsInput:
    gross_reward: float
    estimated_hours: float
    estimated_cost: float = 0.0
    fee_percent: float = 0.0
    flat_fee: float = 0.0
    currency: str = "EUR"
    cost_currency: str = "EUR"
    target_hourly_rate: float | None = None


def _amount(name: str, value: float, *, allow_zero: bool = True) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    if value < 0 or (not allow_zero and value <= 0):
        raise ValueError(f"{name} must be {'greater than zero' if not allow_zero else 'zero or greater'}")
    return float(value)


def evaluate_economics(item: EconomicsInput) -> dict:
    """Calculate estimated net reward and hourly return without mixing currencies."""
    gross = _amount("gross_reward", item.gross_reward)
    hours = _amount("estimated_hours", item.estimated_hours, allow_zero=False)
    cost = _amount("estimated_cost", item.estimated_cost)
    fee_percent = _amount("fee_percent", item.fee_percent)
    flat_fee = _amount("flat_fee", item.flat_fee)
    target = None if item.target_hourly_rate is None else _amount("target_hourly_rate", item.target_hourly_rate)

    currency = item.currency.strip().upper()
    cost_currency = item.cost_currency.strip().upper()
    if not re.fullmatch(r"[A-Z]{3}", currency) or not re.fullmatch(r"[A-Z]{3}", cost_currency):
        raise ValueError("currency values must be three-letter currency codes")
    if currency != cost_currency:
        raise ValueError("reward and cost currencies must match; automatic conversion is not performed")
    if fee_percent > 100:
        raise ValueError("fee_percent must be between 0 and 100")

    percentage_fee = gross * fee_percent / 100
    total_cost = cost + flat_fee + percentage_fee
    net = gross - total_cost
    hourly = net / hours
    roi = (net / total_cost * 100) if total_cost > 0 else None
    minimum_reward = None
    target_met = None
    if fee_percent < 100:
        minimum_reward = (cost + flat_fee + (target or 0) * hours) / (1 - fee_percent / 100)
        if target is not None:
            target_met = hourly >= target

    return {
        "currency": currency,
        "gross_reward": round(gross, 2),
        "estimated_cost": round(cost, 2),
        "flat_fee": round(flat_fee, 2),
        "percentage_fee": round(percentage_fee, 2),
        "total_cost": round(total_cost, 2),
        "estimated_net": round(net, 2),
        "estimated_hours": round(hours, 2),
        "estimated_net_per_hour": round(hourly, 2),
        "roi_percent": None if roi is None else round(roi, 2),
        "target_hourly_rate": target,
        "target_met": target_met,
        "minimum_gross_reward_for_target": None if minimum_reward is None else round(minimum_reward, 2),
        "assessment": "positive" if net > 0 else "break_even" if net == 0 else "negative",
        "verified": False,
        "disclaimer": "Estimate based only on the amounts and fees you entered. Taxes, currency conversion, payout restrictions and actual payment are not verified.",
    }
