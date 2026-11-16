import pytest

from app.game_engine import authorize_game_strategy, solve_target_number


def test_target_number_solver_finds_exact_expression():
    result = solve_target_number([2, 3, 4], 14)
    assert result["solved"] is True
    assert result["expression"]
    assert result["external_action_taken"] is False


def test_target_number_solver_reports_unsolved_round():
    result = solve_target_number([1, 1], 99)
    assert result["solved"] is False
    assert result["expression"] is None


@pytest.mark.parametrize("numbers,target", [([1], 1), ([1] * 8, 8), ([1, -2], 1), ([1, 2], 10001)])
def test_target_number_solver_rejects_out_of_bounds_input(numbers, target):
    with pytest.raises(ValueError):
        solve_target_number(numbers, target)


def test_authorization_requires_explicit_skill_game_policy():
    authorize_game_strategy({
        "opportunity_category": "skill_contest",
        "automation_policy": "allowed",
        "captcha_required": False,
        "automation_eligibility": "auto",
        "policy_evidence_url": "https://example.com/terms",
    })


@pytest.mark.parametrize("changes", [
    {"automation_policy": "unknown"},
    {"automation_policy": "prohibited"},
    {"captcha_required": True},
    {"captcha_required": None},
    {"automation_eligibility": "manual_only"},
    {"opportunity_category": "ordinary"},
    {"policy_evidence_url": ""},
])
def test_authorization_fails_closed(changes):
    opportunity = {
        "opportunity_category": "skill_contest",
        "automation_policy": "allowed",
        "captcha_required": False,
        "automation_eligibility": "auto",
        "policy_evidence_url": "https://example.com/terms",
    }
    opportunity.update(changes)
    with pytest.raises(PermissionError):
        authorize_game_strategy(opportunity)
