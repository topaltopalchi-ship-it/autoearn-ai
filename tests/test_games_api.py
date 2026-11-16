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
