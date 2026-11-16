"""Local deduction helpers for word and code-breaking skill puzzles.

These functions analyze user-supplied puzzle state only; they never interact with websites.
"""
from __future__ import annotations

from itertools import product
from typing import Any


def wordle_feedback(answer: str, guess: str) -> str:
    """Return Wordle-style feedback: G=exact, Y=present elsewhere, .=absent."""
    if len(answer) != len(guess) or not answer.isalpha() or not guess.isalpha():
        raise ValueError("Answer and guess must be alphabetic words of equal length.")
    answer = answer.lower()
    guess = guess.lower()
    marks = ["."] * len(answer)
    remaining: dict[str, int] = {}
    for i, (a, g) in enumerate(zip(answer, guess)):
        if a == g:
            marks[i] = "G"
        else:
            remaining[a] = remaining.get(a, 0) + 1
    for i, g in enumerate(guess):
        if marks[i] == "G":
            continue
        if remaining.get(g, 0):
            marks[i] = "Y"
            remaining[g] -= 1
    return "".join(marks)


def filter_word_candidates(candidates: list[str], guesses: list[dict[str, str]]) -> dict[str, Any]:
    """Filter a bounded candidate list using exact Wordle-style feedback patterns."""
    if not 1 <= len(candidates) <= 5000:
        raise ValueError("Provide between 1 and 5000 candidate words.")
    normalized = [word.lower() for word in candidates]
    if any(not word.isalpha() or len(word) != len(normalized[0]) for word in normalized):
        raise ValueError("All candidate words must be alphabetic and have the same length.")
    if len(set(normalized)) != len(normalized):
        raise ValueError("Candidate words must be unique.")
    if len(guesses) > 20:
        raise ValueError("At most 20 guess/feedback pairs are supported.")

    for item in guesses:
        guess = item.get("guess", "").lower()
        feedback = item.get("feedback", "").upper()
        if len(guess) != len(normalized[0]) or not guess.isalpha():
            raise ValueError("Each guess must match the candidate word length.")
        if len(feedback) != len(guess) or any(mark not in "GY." for mark in feedback):
            raise ValueError("Feedback must use G, Y, and . with one mark per letter.")

    remaining = [
        word for word in normalized
        if all(wordle_feedback(word, item["guess"]) == item["feedback"].upper() for item in guesses)
    ]
    return {
        "candidate_count": len(normalized),
        "remaining_count": len(remaining),
        "candidates": remaining,
        "mode": "local_deduction_only",
        "external_action_taken": False,
    }


def mastermind_feedback(secret: tuple[str, ...], guess: tuple[str, ...]) -> tuple[int, int]:
    """Return (exact-position matches, color-only matches), duplicates included."""
    exact = sum(a == b for a, b in zip(secret, guess))
    secret_rest = [a for a, b in zip(secret, guess) if a != b]
    guess_rest = [b for a, b in zip(secret, guess) if a != b]
    colors = sum(min(secret_rest.count(color), guess_rest.count(color)) for color in set(secret_rest))
    return exact, colors


def solve_mastermind(
    colors: list[str],
    length: int,
    history: list[dict[str, Any]],
    max_candidates: int = 100000,
) -> dict[str, Any]:
    """Enumerate possible codes consistent with exact/misplaced feedback."""
    palette = [color.strip().lower() for color in colors]
    if not 2 <= len(palette) <= 8 or any(not c or len(c) > 20 for c in palette):
        raise ValueError("Provide 2 to 8 non-empty color names (max 20 chars each).")
    if len(set(palette)) != len(palette):
        raise ValueError("Color names must be unique.")
    if type(length) is not int or not 2 <= length <= 6:
        raise ValueError("Code length must be an integer from 2 to 6.")
    total = len(palette) ** length
    if total > max_candidates:
        raise ValueError("Search space is too large; use fewer colors or a shorter code.")
    if len(history) > 20:
        raise ValueError("At most 20 feedback rows are supported.")

    normalized_history: list[tuple[tuple[str, ...], int, int]] = []
    for row in history:
        guess = tuple(str(c).lower() for c in row.get("guess", []))
        exact = row.get("exact")
        misplaced = row.get("misplaced")
        if len(guess) != length or any(c not in palette for c in guess):
            raise ValueError("Every historical guess must use valid colors and match code length.")
        if type(exact) is not int or type(misplaced) is not int or exact < 0 or misplaced < 0 or exact + misplaced > length:
            raise ValueError("Feedback counts must be non-negative integers totaling at most code length.")
        normalized_history.append((guess, exact, misplaced))

    possible = []
    for secret in product(palette, repeat=length):
        if all(mastermind_feedback(secret, guess) == (exact, misplaced)
               for guess, exact, misplaced in normalized_history):
            possible.append(list(secret))
    return {
        "possible_count": len(possible),
        "possible_codes": possible[:100],
        "truncated": len(possible) > 100,
        "search_space": total,
        "mode": "local_deduction_only",
        "external_action_taken": False,
    }
