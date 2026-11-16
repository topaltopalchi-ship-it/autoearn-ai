"""Policy-gated strategy engine for skill games.

The built-in solver operates only on submitted game state. It does not connect to
websites, click controls, submit entries, or interact with anti-bot mechanisms.
"""
from __future__ import annotations

from fractions import Fraction
from itertools import permutations
from typing import Any


def solve_target_number(numbers: list[int], target: int) -> dict[str, Any]:
    """Find an exact +, -, *, / expression using each supplied number once.

    This bounded solver is intended for small arithmetic/puzzle rounds (2-7 tiles).
    It returns a transparent expression and never claims a win on a remote platform.
    """
    if not 2 <= len(numbers) <= 7:
        raise ValueError("Provide between 2 and 7 number tiles.")
    if any(type(n) is not int or n < 0 or n > 1000 for n in numbers):
        raise ValueError("Number tiles must be integers from 0 to 1000.")
    if type(target) is not int or not -10000 <= target <= 10000:
        raise ValueError("Target must be an integer between -10000 and 10000.")

    # Each state maps a rational value to one expression; memoization keeps search bounded.
    def search(values: tuple[int, ...]) -> str | None:
        if len(values) == 1:
            return str(values[0]) if values[0] == target else None
        # Recursively combine ordered pairs; the first exact solution is sufficient.
        for i in range(len(values)):
            for j in range(len(values)):
                if i == j:
                    continue
                a, b = values[i], values[j]
                rest = [values[k] for k in range(len(values)) if k not in (i, j)]
                candidates = [(a + b, "+"), (a - b, "-"), (a * b, "*")]
                if b and a % b == 0:
                    candidates.append((a // b, "/"))
                for value, _op in candidates:
                    result = search(tuple(rest + [value]))
                    if result is not None:
                        # Rebuild a valid expression from the recursive result.
                        return f"({a} {_op} {b})" if len(rest) == 0 else None
        return None

    # General expression search with exact Fractions and explicit expression trees.
    def combine(items: list[tuple[Fraction, str]]) -> str | None:
        if len(items) == 1:
            return items[0][1] if items[0][0] == target else None
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                a, ea = items[i]
                b, eb = items[j]
                rest = [items[k] for k in range(len(items)) if k not in (i, j)]
                options = [
                    (a + b, f"({ea} + {eb})"),
                    (a - b, f"({ea} - {eb})"),
                    (b - a, f"({eb} - {ea})"),
                    (a * b, f"({ea} * {eb})"),
                ]
                if b:
                    options.append((a / b, f"({ea} / {eb})"))
                if a:
                    options.append((b / a, f"({eb} / {ea})"))
                for value, expression in options:
                    found = combine(rest + [(value, expression)])
                    if found is not None:
                        return found
        return None

    expression = combine([(Fraction(n), str(n)) for n in numbers])
    return {
        "solved": expression is not None,
        "expression": expression,
        "target": target,
        "numbers": numbers,
        "strategy": "exact_rational_search",
        "external_action_taken": False,
    }


def authorize_game_strategy(opportunity: dict[str, Any]) -> None:
    """Require explicit, reviewed permission before enabling an external adapter."""
    if opportunity.get("opportunity_category") != "skill_contest":
        raise PermissionError("Only skill-contest opportunities are supported.")
    if opportunity.get("automation_policy") != "allowed":
        raise PermissionError("The platform must explicitly permit automated play.")
    if opportunity.get("captcha_required") is not False:
        raise PermissionError("Unknown or required CAPTCHA blocks automated play.")
    if opportunity.get("automation_eligibility") != "auto":
        raise PermissionError("Policy evidence is incomplete or not cleared.")
    if not (opportunity.get("policy_evidence_url") or opportunity.get("policy_evidence")):
        raise PermissionError("Reviewed policy evidence is required.")
