"""Mwmbl Search API adapter for opportunity-discovery prototypes.

The adapter supports an optional API key. Authentication requirements,
availability, and usage limits must be confirmed against current provider
documentation before relying on this integration.
"""
from __future__ import annotations

import json
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from autoearn.opportunities import SearchResult

ENDPOINT = "https://api.mwmbl.org/api/v2/search/"
_ANONYMOUS_INTERVAL_SECONDS = 1.0
_rate_lock = threading.Lock()
_last_request_at = 0.0


def _respect_anonymous_rate_limit() -> None:
    """Serialize anonymous calls to no more than one request per second per process."""
    global _last_request_at
    with _rate_lock:
        now = time.monotonic()
        wait = _ANONYMOUS_INTERVAL_SECONDS - (now - _last_request_at)
        if wait > 0:
            time.sleep(wait)
        _last_request_at = time.monotonic()


class MwmblSearchProvider:
    """Search adapter for Mwmbl v2 with optional API-key configuration."""

    def __init__(self, api_key: str | None = None, timeout: float = 10.0):
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self.api_key = api_key.strip() if api_key and api_key.strip() else None
        self.timeout = timeout

    def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must not be empty")
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 50:
            raise ValueError("limit must be an integer from 1 to 50")

        if self.api_key is None:
            _respect_anonymous_rate_limit()

        headers = {
            "Accept": "application/json",
            "User-Agent": "AutoEarnAI/0.1 (opportunity discovery prototype)",
        }
        if self.api_key:
            headers["X-API-Key"] = self.api_key

        request = Request(
            ENDPOINT + "?" + urlencode({"q": query.strip()}),
            headers=headers,
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read(2_000_000).decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, ValueError, OSError) as exc:
            raise RuntimeError("Mwmbl search request failed") from exc

        rows = payload.get("results", []) if isinstance(payload, dict) else payload
        if not isinstance(rows, list):
            raise RuntimeError("Mwmbl returned an unexpected response")
        output = []
        for row in rows[:limit]:
            if not isinstance(row, dict):
                continue
            title = row.get("title", "")
            if isinstance(title, list):
                title = "".join(
                    str(part.get("value", "")) if isinstance(part, dict) else str(part)
                    for part in title
                )
            snippet = row.get("content", row.get("extract", row.get("snippet", "")))
            output.append(
                SearchResult(
                    title=str(title),
                    url=str(row.get("url", "")),
                    snippet=str(snippet)[:2000],
                    provider="mwmbl",
                )
            )
        return output
