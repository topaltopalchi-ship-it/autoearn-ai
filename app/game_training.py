"""Offline skill-game practice simulator.

The simulator runs only bundled puzzles in-process. It does not access websites,
accounts, prizes, payments, or external game sessions.
"""
from __future__ import annotations

from statistics import median
from time import perf_counter
from typing import Any

from app.game_engine import solve_target_number

# A deterministic mixed set keeps practice results reproducible.
_PUZZLES: tuple[tuple[tuple[int, ...], int], ...] = (
    ((2, 3, 4), 14),
    ((5, 5, 5), 15),
    ((10, 25, 3, 2), 75),
    ((4, 4, 4), 12),
    ((7, 8), 15),
    ((9, 2, 2), 5),
    ((1, 1), 99),
    ((2, 2, 2), 7),
    ((6, 6), 5),
    ((3, 3, 8), 24),
)


def run_offline_practice(rounds: int = 10) -> dict[str, Any]:
    """Automatically solve a bounded number of local practice puzzles."""
    if type(rounds) is not int or not 1 <= rounds <= len(_PUZZLES):
        raise ValueError(f"rounds must be an integer from 1 to {len(_PUZZLES)}")

    timings: list[float] = []
    solved = 0
    details = []
    for index, (numbers, target) in enumerate(_PUZZLES[:rounds], start=1):
        started = perf_counter()
        result = solve_target_number(list(numbers), target)
        elapsed = (perf_counter() - started) * 1000
        timings.append(elapsed)
        solved += int(result["solved"])
        details.append({
            "round": index,
            "numbers": list(numbers),
            "target": target,
            "solved": bool(result["solved"]),
            "expression": result.get("expression"),
            "latency_ms": round(elapsed, 3),
        })

    return {
        "mode": "offline_practice",
        "rounds": rounds,
        "solved": solved,
        "unsolved": rounds - solved,
        "solve_rate": round(solved / rounds, 4),
        "latency_ms_median": round(median(timings), 3),
        "results": details,
        "external_actions": 0,
        "site_played": False,
        "prize_or_earnings": 0,
        "note": "Local practice only. This metric is not a real-world competition win rate.",
    }
