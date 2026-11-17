"""Currency-aware ranking for the latest reviewed opportunity evaluations.

Scores are screening signals, not earnings forecasts. Amounts in different
currencies are intentionally kept in separate groups until FX evidence exists.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any


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
        if eligibility == "eligible" and not stale and score >= 70:
            tier = "priority_candidate"
        elif eligibility != "ineligible" and score >= 35:
            tier = "needs_review"
        else:
            tier = "low_priority"
        flags = evaluation.get("risk_flags") or []
        item = {
            **record,
            "currency_group": currency,
            "ranking_score": score,
            "priority_tier": tier,
            "execution_allowed": bool(evaluation.get("execution_allowed", False)),
            "execution_authorized": False,
            "risk_flag_count": len(flags) if isinstance(flags, list) else 0,
        }
        grouped[currency].append(item)

    tier_order = {"priority_candidate": 0, "needs_review": 1, "low_priority": 2}
    groups = []
    for currency in sorted(grouped):
        items = sorted(
            grouped[currency],
            key=lambda item: (
                tier_order[item["priority_tier"]],
                -item["ranking_score"],
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
