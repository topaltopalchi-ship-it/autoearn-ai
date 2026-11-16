import pytest

from app.strategy_engine import recommend_strategy


def test_ucb1_explores_untried_strategies_before_exploitation():
    result = recommend_strategy(
        ["fast", "accurate"],
        [{"strategy": "fast", "reward": 0.7}],
    )
    assert result["selected_strategy"] == "accurate"
    assert result["selection_reason"] == "explore_untried_strategy"
    assert result["external_actions"] == 0
    assert result["site_played"] is False


def test_ucb1_selects_best_estimated_strategy_after_initial_exploration():
    history = (
        [{"strategy": "fast", "reward": 0.2}] * 20
        + [{"strategy": "accurate", "reward": 0.9}] * 20
    )
    result = recommend_strategy(["fast", "accurate"], history, exploration=0)
    assert result["selected_strategy"] == "accurate"
    assert result["algorithm"] == "ucb1"


@pytest.mark.parametrize("candidates,history,exploration", [
    ([], [], 2), (["x", "x"], [], 2), (["x"], [{"strategy": "bad", "reward": 1}], 2),
    (["x"], [{"strategy": "x", "reward": 2}], 2), (["x"], [], 9),
])
def test_ucb1_rejects_invalid_inputs(candidates, history, exploration):
    with pytest.raises(ValueError):
        recommend_strategy(candidates, history, exploration)
