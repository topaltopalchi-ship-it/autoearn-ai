"""Evidence-based triage for newly discovered leads.

This is a research queue, not an earnings or country-eligibility ranking.
Unknown payout, country eligibility and AI permission remain explicitly unknown.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .tracks import get_track, track_matches_category


def _age_days(value: str) -> int | None:
    if not value:
        return None
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        age_seconds = (datetime.now(timezone.utc) - stamp.astimezone(timezone.utc)).total_seconds()
        # Any future timestamp is invalid for freshness, including clock skew
        # smaller than one day. Never award freshness points to future data.
        if age_seconds < 0:
            return None
        return int(age_seconds // 86400)
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
        country_status = str(record.get("research_country_status") or "unknown")
        payout_status = str(record.get("research_payout_status") or "unknown")
        ai_status = str(record.get("research_ai_permission") or "unknown")
        if country_status == "blocked":
            country_eligibility = "ineligible"
        elif country_status == "verified":
            country_eligibility = "eligible"
        else:
            country_eligibility = "unknown"

        if payout_status == "unavailable":
            payout_availability = "unavailable"
        elif payout_status == "verified":
            payout_availability = "available"
        else:
            payout_availability = "unknown"

        if country_status == "blocked":
            participation_readiness = "blocked_country"
            readiness_rank = 2
            readiness_score = 0
        elif payout_status == "unavailable":
            participation_readiness = "blocked_payout"
            readiness_rank = 3
            readiness_score = 0
        elif country_status == "verified" and payout_status == "verified":
            participation_readiness = "country_and_payout_verified"
            readiness_rank = 0
            readiness_score = 100
        else:
            participation_readiness = "needs_country_or_payout_research"
            readiness_rank = 1
            readiness_score = 50 if country_status == "verified" or payout_status == "verified" else 0

        if ai_status == "allowed":
            automation_policy = "ai_allowed_subject_to_task_rules"
        elif ai_status == "prohibited":
            automation_policy = "manual_only"
        else:
            automation_policy = "policy_unverified"

        # Only a human-reviewed, category-compatible track may influence tie-breaking.
        # Auto-inferred or stale/mismatched labels remain informationally untrusted.
        track_key = str(record.get("track_key") or "").strip()
        reviewed_track = (
            get_track(track_key)
            if record.get("track_review_status") == "matched"
            and track_matches_category(track_key, str(record.get("category") or ""))
            else None
        )
        track_priority = reviewed_track.priority if reviewed_track else 999

        items.append({
            **record,
            "track_label": reviewed_track.label if reviewed_track else "نیازمند بررسی دسته‌بندی",
            "track_priority": track_priority,
            "track_execution_guidance": reviewed_track.execution_guidance if reviewed_track else "unreviewed",
            "research_priority_score": score,
            "research_priority": tier,
            "research_reasons": reasons,
            "feed_reliability_percent": reliability,
            "country_eligibility": country_eligibility,
            "payout_availability": payout_availability,
            "ai_permission": ai_status,
            "participation_readiness": participation_readiness,
            "participation_readiness_score": readiness_score,
            "participation_readiness_rank": readiness_rank,
            "automation_policy": automation_policy,
            "financial_evaluation_status": "not_evaluated",
            "next_research_actions": [
                "بررسی پشتیبانی رسمی از کشور محل فعالیت",
                "تأیید روش برداشت پول برای همان کشور",
                "ثبت حداقل برداشت، کارمزدها و ارز تسویه",
                "بررسی مجوز صریح استفاده از هوش مصنوعی و خودکارسازی",
                "بررسی وجود API رسمی و شرایط دسترسی",
            ],
            "execution_authorized": False,
        })

    order = {"research_first": 0, "review": 1, "low_signal": 2}
    items.sort(key=lambda item: (
        item["participation_readiness_rank"],
        order[item["research_priority"]],
        -item["research_priority_score"],
        item["track_priority"],
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
