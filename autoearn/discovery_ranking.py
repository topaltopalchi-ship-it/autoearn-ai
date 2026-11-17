"""Evidence-based triage for newly discovered leads.

This is a research queue, not an earnings or country-eligibility ranking.
Unknown payout, country eligibility and AI permission remain explicitly unknown.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _age_days(value: str) -> int | None:
    if not value:
        return None
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        age_seconds = (datetime.now(timezone.utc) - stamp.astimezone(timezone.utc)).total_seconds()
        if age_seconds < -86400:
            return None
        return max(0, int(age_seconds // 86400))
    except (TypeError, ValueError):
        return None


def prioritize_discovery_leads(records: list[dict[str, Any]]) -> dict[str, Any]:
    items = []
    for record in records:
        score = 0
        reasons: list[str] = []
        if record.get("terms_url"):
            score += 30
            reasons.append("لینک شرایط و قوانین موجود است")
        else:
            reasons.append("لینک شرایط و قوانین ثبت نشده است")

        summary = str(record.get("summary") or "").strip()
        if len(summary) >= 120:
            score += 15
            reasons.append("توضیحات اولیه نسبتاً کامل است")
        elif summary:
            score += 7
            reasons.append("توضیحات اولیه کوتاه است")
        else:
            reasons.append("توضیح کافی موجود نیست")

        if record.get("feed_status") == "approved":
            score += 25
            reasons.append("خبرخوان منبع قبلاً تأیید شده است")
        else:
            reasons.append("منبع یا خبرخوان هنوز تأیید نشده است")

        checks = int(record.get("total_checks") or 0)
        successes = int(record.get("total_successes") or 0)
        if checks >= 5:
            reliability = round((successes / checks) * 100) if checks else 0
            if reliability >= 80:
                score += 20
                reasons.append("سابقهٔ موفقیت خبرخوان قابل‌قبول است")
            elif reliability >= 50:
                score += 10
                reasons.append("سابقهٔ خبرخوان متوسط است")
            else:
                reasons.append("سابقهٔ خبرخوان ضعیف است")
        else:
            reliability = None
            reasons.append("نمونهٔ کافی برای سنجش سابقهٔ خبرخوان وجود ندارد")

        age = _age_days(str(record.get("last_seen_at") or record.get("observed_at") or ""))
        if age is not None and age <= 7:
            score += 10
            reasons.append("فرصت در هفت روز اخیر مشاهده شده است")
        else:
            reasons.append("تازگی فرصت تأیید نشده یا بیش از هفت روز است")

        score = min(100, score)
        tier = "research_first" if score >= 70 else "review" if score >= 40 else "low_signal"
        items.append({
            **record,
            "research_priority_score": score,
            "research_priority": tier,
            "research_reasons": reasons,
            "feed_reliability_percent": reliability,
            "country_eligibility": "unknown",
            "payout_availability": "unknown",
            "ai_permission": "unknown",
            "financial_evaluation_status": "not_evaluated",
            "execution_authorized": False,
        })

    order = {"research_first": 0, "review": 1, "low_signal": 2}
    items.sort(key=lambda item: (
        order[item["research_priority"]],
        -item["research_priority_score"],
        str(item.get("title", "")).casefold(),
        int(item.get("id") or 0),
    ))
    return {
        "items": items,
        "total": len(items),
        "note": (
            "این امتیاز فقط اولویت بررسی مدارک و کیفیت منبع را نشان می‌دهد؛ "
            "واجدشرایط‌بودن کشور، امکان برداشت پول، درآمد و مجوز AI هنوز تأیید نشده‌اند."
        ),
    }
