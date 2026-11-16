from fastapi.testclient import TestClient

from app.main import app


def test_game_solver_requires_explicit_policy_and_records_local_stats(tmp_path, monkeypatch):
    from app import main
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "games.db")
    main.init_db()
    with TestClient(app) as client:
        blocked = client.post("/api/opportunities", json={
            "title": "Unreviewed skill game", "platform": "Example",
            "url": "https://example.com/skill"
        })
        assert blocked.status_code == 201
        denied = client.post("/api/games/solve", json={
            "opportunity_id": blocked.json()["id"], "numbers": [2, 3, 4], "target": 14
        })
        assert denied.status_code == 403

        allowed = client.post("/api/opportunities", json={
            "title": "Permitted number challenge", "platform": "Example",
            "url": "https://example.com/skill-2",
            "opportunity_category": "skill_contest",
            "automation_policy": "allowed",
            "captcha_required": False,
            "policy_source": "terms",
            "policy_evidence_url": "https://example.com/terms"
        })
        assert allowed.status_code == 201
        solved = client.post("/api/games/solve", json={
            "opportunity_id": allowed.json()["id"], "numbers": [2, 3, 4], "target": 14
        })
        assert solved.status_code == 200
        assert solved.json()["solved"] is True
        assert solved.json()["site_played"] is False
        stats = client.get("/api/games/stats").json()
        assert stats["attempts"] == 1
        assert stats["solved"] == 1
        assert stats["metric"] == "local_puzzle_solve_rate_not_platform_win_rate"


def test_word_and_logic_apis_are_policy_gated_and_local_only(tmp_path, monkeypatch):
    from app import main
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "deduction.db")
    main.init_db()
    with TestClient(app) as client:
        blocked = client.post("/api/opportunities", json={
            "title": "Unreviewed word game", "platform": "Example",
            "url": "https://example.com/word"
        })
        payload = {"opportunity_id": blocked.json()["id"], "candidates": ["apple", "ample"],
                   "guesses": [{"guess": "allee", "feedback": "GY..G"}]}
        assert client.post("/api/games/word/filter", json=payload).status_code == 403

        allowed = client.post("/api/opportunities", json={
            "title": "Permitted deduction contest", "platform": "Example",
            "url": "https://example.com/deduction",
            "opportunity_category": "skill_contest",
            "automation_policy": "allowed", "captcha_required": False,
            "policy_source": "terms", "policy_evidence_url": "https://example.com/terms"
        })
        opportunity_id = allowed.json()["id"]
        payload["opportunity_id"] = opportunity_id
        word = client.post("/api/games/word/filter", json=payload)
        assert word.status_code == 200
        assert word.json()["candidates"] == ["apple", "ample"]
        assert word.json()["external_action_taken"] is False

        logic = client.post("/api/games/logic/mastermind", json={
            "opportunity_id": opportunity_id,
            "colors": ["red", "blue", "green"], "length": 2,
            "history": [{"guess": ["red", "blue"], "exact": 1, "misplaced": 0}]
        })
        assert logic.status_code == 200
        assert logic.json()["possible_count"] == 4
        assert logic.json()["external_action_taken"] is False


def test_offline_practice_endpoint_runs_without_opportunity_or_external_actions():
    with TestClient(app) as client:
        response = client.get("/api/games/practice?rounds=3")
        assert response.status_code == 200
        payload = response.json()
        assert payload["mode"] == "offline_practice"
        assert payload["rounds"] == 3
        assert payload["external_actions"] == 0
        assert payload["site_played"] is False
        assert payload["prize_or_earnings"] == 0


def test_offline_practice_endpoint_bounds_round_count():
    with TestClient(app) as client:
        assert client.get("/api/games/practice?rounds=11").status_code == 422



def test_memory_practice_endpoint_is_local_and_bounded():
    with TestClient(app) as client:
        response = client.get("/api/games/memory-practice?rounds=3")
        assert response.status_code == 200
        payload = response.json()
        assert payload["mode"] == "offline_memory_practice"
        assert payload["rounds"] == 3
        assert payload["external_actions"] == 0
        assert payload["site_played"] is False
        assert payload["prize_or_earnings"] == 0
        assert client.get("/api/games/memory-practice?rounds=7").status_code == 422


def test_strategy_recommendation_api_uses_only_local_history():
    with TestClient(app) as client:
        response = client.post("/api/games/strategy/recommend", json={
            "candidates": ["fast", "accurate"],
            "history": [{"strategy": "fast", "reward": 0.4}],
        })
        assert response.status_code == 200
        payload = response.json()
        assert payload["selected_strategy"] == "accurate"
        assert payload["external_actions"] == 0
        assert payload["site_played"] is False


def test_strategy_recommendation_api_rejects_invalid_observations():
    with TestClient(app) as client:
        response = client.post("/api/games/strategy/recommend", json={
            "candidates": ["fast"],
            "history": [{"strategy": "unknown", "reward": 0.8}],
        })
        assert response.status_code == 422


def test_strategy_observations_persist_and_feed_game_specific_recommendations(tmp_path, monkeypatch):
    from app import main
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "strategy-memory.db")
    main.init_db()
    with TestClient(app) as client:
        for strategy, reward in [("careful", 0.9), ("risky", 0.1)]:
            for _ in range(4):
                response = client.post("/api/games/strategy/observe", json={
                    "game_type": "number", "strategy": strategy, "reward": reward,
                    "duration_ms": 1200,
                })
                assert response.status_code == 201
                assert response.json()["external_actions"] == 0

        # A separate game type must not inherit the number-game observations.
        recommendation = client.post("/api/games/strategy/recommend", json={
            "game_type": "number", "candidates": ["careful", "risky"],
            "exploration": 0,
        })
        assert recommendation.status_code == 200
        assert recommendation.json()["selected_strategy"] == "careful"
        assert recommendation.json()["observations"] == 8
        assert recommendation.json()["history_source"] == "persisted_local_practice"
        assert recommendation.json()["external_actions"] == 0

        stats = client.get("/api/games/strategy/stats?game_type=number")
        assert stats.status_code == 200
        assert stats.json()["observations"] == 8
        assert stats.json()["strategies"][0]["strategy"] == "careful"
        assert stats.json()["real_world_win_rate"] is None

        word_recommendation = client.post("/api/games/strategy/recommend", json={
            "game_type": "word", "candidates": ["careful", "risky"],
            "exploration": 0,
        })
        assert word_recommendation.status_code == 200
        assert word_recommendation.json()["observations"] == 0
        assert word_recommendation.json()["history_source"] == "persisted_local_practice"


def test_strategy_observation_rejects_out_of_range_reward():
    with TestClient(app) as client:
        response = client.post("/api/games/strategy/observe", json={
            "game_type": "word", "strategy": "guess-a", "reward": 1.5,
        })
        assert response.status_code == 422


def test_player_status_reports_local_readiness_without_claiming_external_play(tmp_path, monkeypatch):
    from app import main
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "player-status.db")
    main.init_db()
    with TestClient(app) as client:
        response = client.get("/api/player/status")
        assert response.status_code == 200
        payload = response.json()
        assert payload["mode"] == "local_practice_and_readiness"
        assert payload["game_attempts"] == 0
        assert payload["local_solve_rate"] is None
        assert payload["strategy_observations"] == 0
        assert payload["external_gameplay_enabled"] is False
        assert payload["automated_payment_enabled"] is False
        assert payload["real_world_win_rate"] is None
