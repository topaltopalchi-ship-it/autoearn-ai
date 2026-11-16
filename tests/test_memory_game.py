from app.memory_game import run_memory_practice


def test_memory_practice_is_bounded_and_local_only():
    result = run_memory_practice(4)
    assert result["mode"] == "offline_memory_practice"
    assert result["rounds"] == 4
    assert result["correct_rounds"] + result["incorrect_rounds"] == 4
    assert 0 <= result["round_accuracy"] <= 1
    assert result["symbols_tested"] > 0
    assert result["external_actions"] == 0
    assert result["site_played"] is False
    assert result["prize_or_earnings"] == 0


def test_memory_practice_rejects_invalid_round_counts():
    for value in (0, 7, True, 1.5):
        try:
            run_memory_practice(value)
        except ValueError:
            pass
        else:
            raise AssertionError(f"Expected ValueError for rounds={value!r}")
