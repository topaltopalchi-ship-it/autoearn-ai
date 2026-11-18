"""Read-only discovery clients for documented public game APIs.

No account login, gameplay, tournament joining, or prize claims are performed.
"""
from __future__ import annotations

from datetime import datetime, timezone
import http.client
import json
import re
import ssl
from threading import Lock
from typing import Any
from urllib.parse import quote


class GamePlatformError(RuntimeError):
    """A public game API could not be queried safely."""


_REQUEST_LOCK = Lock()
_MAX_RESPONSE_BYTES = 512 * 1024
_USER_AGENT = "AutoEarn-AI/0.1 (read-only game discovery)"


def _get_json(host: str, path: str) -> dict[str, Any] | list[Any]:
    if host not in {"lichess.org", "api.chess.com"}:
        raise GamePlatformError("Unapproved game API host.")
    if not path.startswith("/") or "\r" in path or "\n" in path:
        raise GamePlatformError("Invalid API path.")
    connection = None
    # Both providers ask clients to avoid parallel bursts. Serialize requests.
    with _REQUEST_LOCK:
        try:
            connection = http.client.HTTPSConnection(
                host, timeout=12, context=ssl.create_default_context()
            )
            connection.request(
                "GET", path,
                headers={
                    "Accept": "application/json",
                    "User-Agent": _USER_AGENT,
                },
            )
            response = connection.getresponse()
            if response.status == 429:
                raise GamePlatformError("Provider rate limit reached; retry later.")
            if response.status != 200:
                raise GamePlatformError("Provider returned a non-success response.")
            payload = response.read(_MAX_RESPONSE_BYTES + 1)
            if len(payload) > _MAX_RESPONSE_BYTES:
                raise GamePlatformError("Provider response exceeded the size limit.")
            try:
                data = json.loads(payload.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise GamePlatformError("Provider returned invalid JSON.") from exc
            if not isinstance(data, (dict, list)):
                raise GamePlatformError("Provider returned an unsupported JSON shape.")
            return data
        except GamePlatformError:
            raise
        except (OSError, ssl.SSLError, http.client.HTTPException, TimeoutError) as exc:
            raise GamePlatformError("Could not reach the public game API.") from exc
        finally:
            if connection is not None:
                connection.close()


def _text(value: Any, limit: int = 180) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.split())[:limit]


def _event(
    provider: str, event_id: str, title: str, url: str, status: str
) -> dict[str, Any]:
    return {
        "platform": provider,
        "event_id": _text(event_id, 120),
        "title": _text(title) or "Untitled event",
        "url": url,
        "status": _text(status, 40) or "unknown",
        "country": "Iran",
        "eligibility": "unknown",
        "payout_readiness": "unknown",
        "participation_mode": "manual_review_only",
        "discovered_at": datetime.now(timezone.utc).isoformat(),
        "source": "official_public_api",
        "review_required": True,
    }


def fetch_lichess_tournaments() -> list[dict[str, Any]]:
    """Fetch public Lichess Arena tournament metadata only."""
    data = _get_json("lichess.org", "/api/tournament")
    if not isinstance(data, dict):
        raise GamePlatformError("Unexpected Lichess tournament response.")
    events: list[dict[str, Any]] = []
    for state in ("created", "started", "finished"):
        entries = data.get(state, [])
        if not isinstance(entries, list):
            continue
        for item in entries[:100]:
            if not isinstance(item, dict):
                continue
            event_id = _text(item.get("id"), 120)
            if not re.fullmatch(r"[A-Za-z0-9_-]{1,120}", event_id):
                continue
            title = _text(item.get("fullName") or item.get("name"))
            events.append(_event(
                "Lichess", event_id, title,
                "https://lichess.org/tournament/" + quote(event_id, safe=""),
                state,
            ))
    return events[:200]


def fetch_chesscom_tournament(tournament_id: str) -> dict[str, Any]:
    """Fetch one Chess.com tournament by its public URL identifier."""
    if not isinstance(tournament_id, str) or not re.fullmatch(
        r"[a-zA-Z0-9][a-zA-Z0-9-]{0,119}", tournament_id
    ):
        raise ValueError("Invalid Chess.com tournament identifier.")
    data = _get_json(
        "api.chess.com", "/pub/tournament/" + quote(tournament_id, safe="-")
    )
    if not isinstance(data, dict):
        raise GamePlatformError("Unexpected Chess.com tournament response.")
    title = _text(data.get("name"))
    status = _text(data.get("status"))
    canonical_url = data.get("url")
    if not isinstance(canonical_url, str) or not canonical_url.startswith(
        "https://www.chess.com/tournament/"
    ):
        canonical_url = "https://www.chess.com/tournament/" + quote(
            tournament_id, safe="-"
        )
    return _event("Chess.com", tournament_id, title, canonical_url, status)


def platform_catalog() -> list[dict[str, Any]]:
    return [
        {
            "id": "lichess",
            "name": "Lichess",
            "connection": "public_api",
            "capabilities": ["arena_tournament_discovery", "public_event_metadata"],
            "mode": "read_only",
            "requires_api_key": False,
            "participation_enabled": False,
            "documentation": "https://lichess.org/api",
        },
        {
            "id": "chesscom",
            "name": "Chess.com",
            "connection": "public_api",
            "capabilities": ["public_tournament_details", "public_player_tournament_data"],
            "mode": "read_only",
            "requires_api_key": False,
            "participation_enabled": False,
            "documentation": "https://support.chess.com/en/articles/9650547-what-is-the-pubapi-and-how-do-i-use-it",
        },
    ]
