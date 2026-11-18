import pytest

from autoearn import game_platforms as gp


def test_lichess_tournaments_normalize_public_events(monkeypatch):
    monkeypatch.setattr(gp, "_get_json", lambda host, path: {
        "created": [{"id": "abc123", "fullName": "Weekly Arena"}],
        "started": [{"id": "live_1", "name": "Live Cup"}],
        "finished": "invalid",
    })
    events = gp.fetch_lichess_tournaments()
    assert [event["title"] for event in events] == ["Weekly Arena", "Live Cup"]
    assert events[0]["url"] == "https://lichess.org/tournament/abc123"
    assert all(event["country"] == "Iran" for event in events)
    assert all(event["eligibility"] == "unknown" for event in events)
    assert all(event["review_required"] for event in events)
    assert all(not event.get("participation_enabled", False) for event in events)


def test_lichess_rejects_unexpected_response(monkeypatch):
    monkeypatch.setattr(gp, "_get_json", lambda host, path: [])
    with pytest.raises(gp.GamePlatformError):
        gp.fetch_lichess_tournaments()


def test_chesscom_tournament_is_read_only_and_unknown_eligibility(monkeypatch):
    monkeypatch.setattr(gp, "_get_json", lambda host, path: {
        "name": "Open Daily Tournament",
        "status": "registration",
        "url": "https://www.chess.com/tournament/open-daily",
    })
    event = gp.fetch_chesscom_tournament("open-daily")
    assert event["title"] == "Open Daily Tournament"
    assert event["status"] == "registration"
    assert event["eligibility"] == "unknown"
    assert event["participation_mode"] == "manual_review_only"


@pytest.mark.parametrize("identifier", [
    "../private", "x/y", "https://evil.example", "a?next=evil", "x" * 121, "",
])
def test_chesscom_identifier_rejects_path_and_query_injection(identifier):
    with pytest.raises(ValueError):
        gp.fetch_chesscom_tournament(identifier)


def test_chesscom_untrusted_return_url_is_not_forwarded(monkeypatch):
    monkeypatch.setattr(gp, "_get_json", lambda host, path: {
        "name": "Tournament", "url": "https://evil.example/steal",
    })
    event = gp.fetch_chesscom_tournament("valid-id")
    assert event["url"] == "https://www.chess.com/tournament/valid-id"


def test_platform_catalog_disables_participation():
    catalog = gp.platform_catalog()
    assert {item["id"] for item in catalog} == {"lichess", "chesscom"}
    assert all(item["mode"] == "read_only" for item in catalog)
    assert all(item["participation_enabled"] is False for item in catalog)


def test_api_client_rejects_unapproved_hosts_without_network():
    with pytest.raises(gp.GamePlatformError, match="Unapproved"):
        gp._get_json("evil.example", "/api")
