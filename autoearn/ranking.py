"""Transparent opportunity ranking from explicit, user-supplied metadata.

Scores are comparative hints, not income forecasts or legitimacy guarantees.
Missing evidence is treated as unknown rather than silently assumed positive.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RankingInput:
    estimated_reward: float | None = None
    estimated_hours: float | None = None
    eligible_countries: str = ""
    payout_method: str = ""
    minimum_payout: float | None = None
    risk_score: int | None = None


def _bounded(value: float, low: float = 0, high: float = 100) -> int:
    return round(max(low, min(high, value)))


def rank_opportunity(item: RankingInput, country: str | None = None) -> dict:
    """Return a 0-100 score, coverage, component explanations, and caveats."""
    components: dict[str, int] = {}
    known = 0

    if item.estimated_reward is not None and item.estimated_reward > 0:
        components["reward_information"] = 100
        known += 1
    else:
        components["reward_information"] = 35

    if item.estimated_hours is not None and item.estimated_hours > 0:
        components["time_efficiency"] = _bounded(100 - (item.estimated_hours - 1) * 4, 20, 100)
        known += 1
    else:
        components["time_efficiency"] = 35

    eligible = [part.strip().upper() for part in item.eligible_countries.split(",") if part.strip()]
    if eligible:
        components["country_fit"] = (
            100 if not country or country.strip().upper() in eligible or "ALL" in eligible else 0
        )
        known += 1
    else:
        components["country_fit"] = 35

    payout_details = bool(item.payout_method.strip())
    threshold_details = item.minimum_payout is not None
    if payout_details and threshold_details:
        components["payout_clarity"] = 100
        known += 1
    elif payout_details or threshold_details:
        components["payout_clarity"] = 65
        known += 1
    else:
        components["payout_clarity"] = 35

    if item.risk_score is not None:
        components["risk"] = 100 - _bounded(item.risk_score)
        known += 1
    else:
        components["risk"] = 35

    weights = {
        "reward_information": 20,
        "time_efficiency": 15,
        "country_fit": 25,
        "payout_clarity": 15,
        "risk": 25,
    }
    score = round(sum(components[key] * weight for key, weight in weights.items()) / 100)
    coverage = round(known / len(weights) * 100)
    warnings = []
    if item.estimated_reward is None:
        warnings.append("درآمد تخمینی ثبت نشده؛ مبلغ واقعی قابل پیش‌بینی نیست.")
    if item.estimated_hours is None:
        warnings.append("زمان انجام مشخص نیست؛ بهره‌وری زمانی قابل مقایسه نیست.")
    if not eligible:
        warnings.append("محدودیت کشور نامشخص است؛ پیش از ثبت‌نام شرایط منطقه‌ای را بررسی کنید.")
    if not item.payout_method.strip():
        warnings.append("روش پرداخت مشخص نیست؛ امکان دریافت وجه تأیید نشده است.")
    if item.minimum_payout is None:
        warnings.append("حداقل مبلغ برداشت مشخص نیست.")
    if item.risk_score is None:
        warnings.append("ارزیابی ریسک ثبت نشده؛ امتیاز پایین به معنی معتبر بودن نیست.")
    return {
        "ranking_score": score,
        "data_coverage": coverage,
        "components": [{"code": key, "score": value} for key, value in components.items()],
        "warnings": warnings,
        "currency_note": "مبالغ ارزهای مختلف با یکدیگر تبدیل یا مقایسه نشده‌اند.",
        "disclaimer": "این رتبه‌بندی فقط بر اساس اطلاعات ثبت‌شده است؛ درآمد، پرداخت یا اعتبار هیچ پلتفرمی را تضمین نمی‌کند.",
    }
