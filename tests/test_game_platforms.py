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


def test_chesscom_accepts_leading_hyphen_identifier(monkeypatch):
    requested = []
    monkeypatch.setattr(gp, "_get_json", lambda host, path: (
        requested.append((host, path)) or {"name": "Hyphen Arena"}
    ))
    event = gp.fetch_chesscom_tournament("-arena-2026")
    assert requested == [("api.chess.com", "/pub/tournament/-arena-2026")]
    assert event["event_id"] == "-arena-2026"
    assert event["url"] == "https://www.chess.com/tournament/-arena-2026"


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


def test_lichess_429_enforces_full_minute_before_next_request(monkeypatch):
    class Response:
        def __init__(self, status, payload=b"{}"):
            self.status = status
            self.payload = payload

        def getheader(self, name):
            return None

        def read(self, limit):
            return self.payload

    responses = [Response(429), Response(200, b'{"created": []}')]
    sleeps = []
    requests = []

    class Connection:
        def __init__(self, host, timeout, context):
            self.host = host

        def request(self, method, path, headers):
            requests.append((self.host, method, path, headers))

        def getresponse(self):
            return responses.pop(0)

        def close(self):
            pass

    monkeypatch.setattr(gp.http.client, "HTTPSConnection", Connection)
    monkeypatch.setattr(gp.time, "monotonic", lambda: 100.0)
    monkeypatch.setattr(gp.time, "sleep", sleeps.append)
    gp._COOLDOWN_UNTIL["lichess.org"] = 0.0

    with pytest.raises(gp.GamePlatformError, match="wait 60 seconds"):
        gp._get_json("lichess.org", "/api/tournament")
    assert gp._get_json("lichess.org", "/api/tournament") == {"created": []}
    assert sleeps == [60.0]
    assert requests[0][3]["User-Agent"].startswith("AutoEarn-AI/")
    assert "contact: https://github.com/topaltopalchi-ship-it/autoearn-ai" in requests[0][3]["User-Agent"]
    gp._COOLDOWN_UNTIL["lichess.org"] = 0.0


def test_chesscom_rate_limit_uses_retry_after_when_larger(monkeypatch):
    class Response:
        status = 429

        def getheader(self, name):
            return "90"

        def read(self, limit):
            return b""

    class Connection:
        def __init__(self, host, timeout, context):
            pass

        def request(self, method, path, headers):
            pass

        def getresponse(self):
            return Response()

        def close(self):
            pass

    monkeypatch.setattr(gp.http.client, "HTTPSConnection", Connection)
    monkeypatch.setattr(gp.time, "monotonic", lambda: 10.0)
    gp._COOLDOWN_UNTIL["api.chess.com"] = 0.0
    with pytest.raises(gp.GamePlatformError, match="wait 90 seconds"):
        gp._get_json("api.chess.com", "/pub/tournament/open")
    assert gp._COOLDOWN_UNTIL["api.chess.com"] == 100.0
    gp._COOLDOWN_UNTIL["api.chess.com"] = 0.0
