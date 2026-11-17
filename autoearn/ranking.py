"""Currency-aware ranking for the latest reviewed opportunity evaluations.

Scores are screening signals, not earnings forecasts. Amounts in different
currencies are intentionally kept in separate groups until FX evidence exists.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

RESEARCH_MAX_AGE_DAYS = 30


def research_evidence_is_fresh(research: dict[str, Any]) -> bool:
    """Require a recent owner review; malformed/missing dates fail closed."""
    checked_at = research.get("checked_at")
    if not checked_at:
        return False
    try:
        checked = datetime.fromisoformat(str(checked_at).replace("Z", "+00:00"))
        if checked.tzinfo is None:
            checked = checked.replace(tzinfo=timezone.utc)
        age_seconds = (datetime.now(timezone.utc) - checked.astimezone(timezone.utc)).total_seconds()
        return 0 <= age_seconds <= RESEARCH_MAX_AGE_DAYS * 86400
    except (TypeError, ValueError, OverflowError):
        return False


def rank_evaluations(records: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        evaluation = record.get("evaluation") or {}
        currency = str(evaluation.get("currency") or "UNKNOWN").strip().upper()
        score = evaluation.get("ranking_score")
        try:
            score = max(0, min(100, int(score)))
        except (TypeError, ValueError):
            score = 0
        eligibility = evaluation.get("eligibility", "unknown")
        stale = bool(evaluation.get("evidence_stale", True))
        research = record.get("research") or {}
        research_status = {
            "country": research.get("country_status", "unknown"),
            "payout": research.get("payout_status", "unknown"),
            "ai_permission": research.get("ai_permission", "unknown"),
        }
        research_fresh = research_evidence_is_fresh(research)
        research_complete = (
            research_status["country"] == "verified"
            and research_status["payout"] == "verified"
            and research_status["ai_permission"] == "allowed"
            and research_fresh
        )
        api_required = record.get("execution_mode") == "official_api"
        api_ready = research.get("api_status", "unknown") == "available"
        if not research_complete:
            tier = "blocked_pending_research"
        elif api_required and not api_ready:
            tier = "blocked_api_unverified"
        elif eligibility == "eligible" and not stale and score >= 70:
            tier = "priority_candidate"
        elif eligibility != "ineligible" and score >= 35:
            tier = "needs_review"
        else:
            tier = "low_priority"

        flags = evaluation.get("risk_flags") or []
        ai_assessment = evaluation.get("ai_task_assessment") or {}
        ai_suitability = ai_assessment.get("suitability", "not_assessed")
        if ai_suitability == "ai_draft_candidate":
            ai_fit = "bounded_ai_draft_candidate"
        elif ai_suitability == "blocked":
            ai_fit = "policy_blocked"
        else:
            ai_fit = "human_review_or_policy_check"

        item = {
            **record,
            "currency_group": currency,
            "ranking_score": score,
            "priority_tier": tier,
            "execution_allowed": bool(evaluation.get("execution_allowed", False)),
            "execution_authorized": False,
            "ai_task_suitability": ai_suitability,
            "ai_fit": ai_fit,
            "ai_suitability_score": ai_assessment.get("score"),
            "risk_flag_count": len(flags) if isinstance(flags, list) else 0,
            "research_status": research_status,
            "research_complete": research_complete,
            "research_fresh": research_fresh,
            "research_max_age_days": RESEARCH_MAX_AGE_DAYS,
            "api_research_ready": api_ready,
        }
        grouped[currency].append(item)

    tier_order = {"priority_candidate": 0, "needs_review": 1, "blocked_pending_research": 2, "blocked_api_unverified": 3, "low_priority": 4}
    groups = []
    for currency in sorted(grouped):
        items = sorted(
            grouped[currency],
            key=lambda item: (
                tier_order[item["priority_tier"]],
                -item["ranking_score"],
                item["ai_fit"] != "bounded_ai_draft_candidate",
                not item["execution_allowed"],
                item["risk_flag_count"],
                item.get("title", "").casefold(),
            ),
        )
        for index, item in enumerate(items, start=1):
            item["rank_in_currency"] = index
        groups.append({"currency": currency, "count": len(items), "items": items})

    return {
        "groups": groups,
        "total": sum(group["count"] for group in groups),
        "comparison_note": (
            "Opportunities are ranked only within the same currency. "
            "Different currencies are not compared without a verified exchange rate. "
            "Priority tiers and scores are screening aids, not income guarantees."
        ),
    }
