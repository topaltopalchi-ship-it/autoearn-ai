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


def test_local_benchmark_is_deterministic_and_reports_no_external_actions():
    from app.game_benchmark import run_target_number_benchmark

    result = run_target_number_benchmark()
    assert result["rounds"] == 10
    assert result["accuracy"] == 1.0
    assert result["external_actions"] == 0
    assert result["site_played"] is False
    assert result["latency_ms_median"] >= 0
    assert result["latency_ms_p95"] >= result["latency_ms_median"]


@pytest.mark.parametrize("rounds", [0, 11, True, 1.5])
def test_local_benchmark_rejects_invalid_round_count(rounds):
    from app.game_benchmark import run_target_number_benchmark

    with pytest.raises(ValueError):
        run_target_number_benchmark(rounds)
