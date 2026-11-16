"""Deterministic local benchmark for the target-number skill solver.

Runs only in-process puzzle analysis. It never contacts or plays a third-party game.
"""
from __future__ import annotations

from math import ceil
from statistics import median
from time import perf_counter
from typing import Any

from app.game_engine import solve_target_number


# Each round is deliberately small and deterministic so results are reproducible.
_ROUNDS: tuple[tuple[tuple[int, ...], int, bool], ...] = (
    ((2, 3, 4), 14, True),
    ((1, 1), 99, False),
    ((5, 5, 5), 15, True),
    ((2, 2, 2), 7, False),
    ((10, 25, 3, 2), 75, True),
    ((4, 4, 4), 12, True),
    ((7, 8), 15, True),
    ((6, 6), 5, False),
    ((3, 3, 8), 24, True),
    ((9, 2, 2), 5, True),
)


def run_target_number_benchmark(rounds: int | None = None) -> dict[str, Any]:
    """Run a fixed corpus and report quality/latency without external side effects."""
    if rounds is not None and (type(rounds) is not int or not 1 <= rounds <= len(_ROUNDS)):
        raise ValueError(f"rounds must be an integer from 1 to {len(_ROUNDS)}")

    selected = _ROUNDS[:rounds] if rounds is not None else _ROUNDS
    latencies_ms: list[float] = []
    correct = 0
    solved = 0

    for numbers, target, expected_solved in selected:
        started = perf_counter()
        result = solve_target_number(list(numbers), target)
        latencies_ms.append((perf_counter() - started) * 1000)
        solved += int(result["solved"])
        correct += int(result["solved"] is expected_solved)

    ordered = sorted(latencies_ms)
    p95 = ordered[max(0, ceil(0.95 * len(ordered)) - 1)]
    count = len(selected)
    return {
        "benchmark": "target_number_v1",
        "rounds": count,
        "correct": correct,
        "accuracy": round(correct / count, 4),
        "solved_rounds": solved,
        "local_solve_rate": round(solved / count, 4),
        "latency_ms_median": round(median(latencies_ms), 3),
        "latency_ms_p95": round(p95, 3),
        "external_actions": 0,
        "site_played": False,
        "note": "Deterministic local benchmark; accuracy and solve rate are not platform win rates.",
    }
