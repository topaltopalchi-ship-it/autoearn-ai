"""Deterministic offline memory-game practice; no external game interaction."""
from __future__ import annotations

from time import perf_counter
from typing import Any

# Fixed local sequences make benchmark runs reproducible.
_SEQUENCES: tuple[tuple[str, ...], ...] = (
    ("red", "blue", "green"),
    ("circle", "square", "triangle", "star"),
    ("A", "C", "B", "D", "A"),
    ("north", "east", "south", "west", "north", "west"),
    ("1", "3", "2", "4", "3", "1", "2"),
    ("sun", "moon", "star", "cloud", "rain", "sun", "star", "moon"),
)


def run_memory_practice(rounds: int = 6) -> dict[str, Any]:
    """Replay bounded, bundled sequences and report exact recall performance."""
    if type(rounds) is not int or not 1 <= rounds <= len(_SEQUENCES):
        raise ValueError(f"rounds must be an integer from 1 to {len(_SEQUENCES)}")

    results = []
    started_all = perf_counter()
    correct = 0
    total_symbols = 0
    for index, sequence in enumerate(_SEQUENCES[:rounds], start=1):
        started = perf_counter()
        recalled = tuple(sequence)  # Local solver stores and replays the observed pattern.
        elapsed_ms = (perf_counter() - started) * 1000
        matched = recalled == sequence
        correct += int(matched)
        total_symbols += len(sequence)
        results.append({
            "round": index,
            "sequence_length": len(sequence),
            "correct": matched,
            "symbols_recalled": len(recalled) if matched else 0,
            "latency_ms": round(elapsed_ms, 3),
        })

    return {
        "mode": "offline_memory_practice",
        "rounds": rounds,
        "correct_rounds": correct,
        "incorrect_rounds": rounds - correct,
        "round_accuracy": round(correct / rounds, 4),
        "symbols_tested": total_symbols,
        "elapsed_ms": round((perf_counter() - started_all) * 1000, 3),
        "results": results,
        "external_actions": 0,
        "site_played": False,
        "prize_or_earnings": 0,
        "note": "Local deterministic replay only; not a platform competition win rate.",
    }
