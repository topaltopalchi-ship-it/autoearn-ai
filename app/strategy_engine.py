"""Adaptive strategy selection using a bounded UCB1 multi-armed bandit.

This selector learns only from caller-supplied local practice outcomes. It never
connects to a game site or performs gameplay, account, payment, or prize actions.
"""
from __future__ import annotations

from math import log, sqrt
from typing import Any


def recommend_strategy(
    candidates: list[str],
    history: list[dict[str, Any]],
    exploration: float = 2.0,
) -> dict[str, Any]:
    if not 1 <= len(candidates) <= 20:
        raise ValueError("Provide between 1 and 20 strategy candidates.")
    if len(set(candidates)) != len(candidates) or any(
        not isinstance(name, str) or not name.strip() or len(name) > 80
        for name in candidates
    ):
        raise ValueError("Strategy names must be unique, non-empty strings up to 80 characters.")
    if len(history) > 5000:
        raise ValueError("History is limited to 5000 observations.")
    if isinstance(exploration, bool) or not isinstance(exploration, (int, float)) or not 0 <= exploration <= 5:
        raise ValueError("Exploration must be between 0 and 5.")

    counts = {name: 0 for name in candidates}
    rewards = {name: 0.0 for name in candidates}
    for item in history:
        if not isinstance(item, dict) or item.get("strategy") not in counts:
            raise ValueError("Each observation must reference a supplied strategy.")
        reward = item.get("reward")
        if isinstance(reward, bool) or not isinstance(reward, (int, float)) or not 0 <= reward <= 1:
            raise ValueError("Observation rewards must be numeric values from 0 to 1.")
        name = item["strategy"]
        counts[name] += 1
        rewards[name] += float(reward)

    total = len(history)
    untried = [name for name in candidates if counts[name] == 0]
    if untried:
        selected = untried[0]
        scores = [
            {"strategy": name, "trials": counts[name],
             "mean_reward": round(rewards[name] / counts[name], 4) if counts[name] else None,
             "ucb_score": None if counts[name] == 0 else round(
                 rewards[name] / counts[name] + sqrt(exploration * log(max(total, 1)) / counts[name]), 6
             )}
            for name in candidates
        ]
        reason = "explore_untried_strategy"
    else:
        scores = []
        for name in candidates:
            mean = rewards[name] / counts[name]
            bonus = sqrt(exploration * log(max(total, 1)) / counts[name])
            scores.append({"strategy": name, "trials": counts[name],
                           "mean_reward": round(mean, 4),
                           "ucb_score": round(mean + bonus, 6)})
        selected = max(scores, key=lambda row: row["ucb_score"])["strategy"]
        reason = "highest_ucb_score"

    return {
        "algorithm": "ucb1",
        "selected_strategy": selected,
        "selection_reason": reason,
        "observations": total,
        "ranked_strategies": sorted(
            scores,
            key=lambda row: float("-inf") if row["ucb_score"] is None else row["ucb_score"],
            reverse=True,
        ),
        "mode": "local_practice_recommendation",
        "external_actions": 0,
        "site_played": False,
        "note": "Recommendation from supplied practice observations; not a real-world win prediction.",
    }
