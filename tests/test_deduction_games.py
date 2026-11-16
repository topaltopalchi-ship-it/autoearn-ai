import pytest

from app.deduction_games import (
    filter_word_candidates,
    mastermind_feedback,
    solve_mastermind,
    wordle_feedback,
)


def test_wordle_feedback_handles_duplicate_letters():
    assert wordle_feedback("apple", "allee") == "G.Y.G"


def test_word_filter_respects_duplicate_letter_feedback():
    result = filter_word_candidates(
        ["apple", "ample", "allee", "apply"],
        [{"guess": "allee", "feedback": "G.Y.G"}],
    )
    assert result["candidates"] == ["apple"]
    assert result["external_action_taken"] is False


def test_word_filter_rejects_invalid_feedback():
    with pytest.raises(ValueError):
        filter_word_candidates(["apple"], [{"guess": "allee", "feedback": "G??G."}])


def test_mastermind_feedback_counts_exact_and_misplaced():
    assert mastermind_feedback(("red", "blue", "red", "green"),
                               ("red", "red", "blue", "yellow")) == (1, 2)


def test_mastermind_solver_filters_codes_with_feedback():
    result = solve_mastermind(
        ["red", "blue", "green"],
        2,
        [{"guess": ["red", "blue"], "exact": 1, "misplaced": 0}],
    )
    assert result["possible_count"] == 4
    assert ["red", "red"] in result["possible_codes"]
    assert result["external_action_taken"] is False


@pytest.mark.parametrize("colors,length", [(["red"], 2), (["a", "b"], 1), (["a"] * 9, 2), (["a", "b"], 7)])
def test_mastermind_rejects_invalid_or_duplicate_palette(colors, length):
    with pytest.raises(ValueError):
        solve_mastermind(colors, length, [])


def test_mastermind_rejects_excessive_search_space():
    with pytest.raises(ValueError):
        solve_mastermind(["a", "b", "c", "d", "e", "f", "g", "h"], 6, [])
