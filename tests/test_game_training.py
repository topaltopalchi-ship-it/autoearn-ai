from app.game_training import run_offline_practice


def test_offline_practice_is_deterministic_and_never_uses_external_actions():
    first = run_offline_practice(5)
    second = run_offline_practice(5)

    assert first["mode"] == "offline_practice"
    assert first["rounds"] == 5
    assert first["solved"] + first["unsolved"] == 5
    assert 0 <= first["solve_rate"] <= 1
    assert first["results"] == second["results"]
    assert first["external_actions"] == 0
    assert first["site_played"] is False
    assert first["prize_or_earnings"] == 0


def test_offline_practice_rejects_invalid_round_counts():
    for value in (0, 11, True, 1.5):
        try:
            run_offline_practice(value)
        except ValueError:
            pass
        else:
            raise AssertionError(f"Expected ValueError for rounds={value!r}")
