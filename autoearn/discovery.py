"""Safe intake records for manually supplied public opportunity sources.

This module stores candidate metadata only. It does not fetch pages, bypass
access controls, or perform platform actions.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlsplit
import ipaddress

from .opportunities import normalize_url


def _validate_public_https_url(value: str) -> str:
    """Require a public-looking HTTPS URL for manually submitted sources."""
    canonical = normalize_url(value)
    parsed = urlsplit(canonical)
    if parsed.scheme != "https" or parsed.username or parsed.password:
        raise ValueError("source URLs must use public HTTPS without credentials")
    if parsed.port not in (None, 443):
        raise ValueError("source URLs must use the standard HTTPS port")
    host = (parsed.hostname or "").rstrip(".").lower()
    if not host or host == "localhost" or any(
        host.endswith(suffix)
        for suffix in (".localhost", ".local", ".internal", ".test", ".invalid", ".example")
    ):
        raise ValueError("source URL must use a public hostname")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise ValueError("source URL must use a public DNS hostname")
    if len(host.split(".")) < 2:
        raise ValueError("source URL must use a public DNS hostname")
    return canonical


@dataclass(frozen=True)
class SourceCandidate:
    name: str
    url: str
    category: str = "game_rewards"
    terms_url: str | None = None
    country_notes: str = ""
    payment_notes: str = ""
    discovered_at: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("source name is required")
        _validate_public_https_url(self.url)
        if self.terms_url:
            _validate_public_https_url(self.terms_url)
        if not isinstance(self.category, str) or not self.category.strip():
            raise ValueError("category is required")
        if self.discovered_at:
            try:
                datetime.fromisoformat(self.discovered_at.replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValueError("discovered_at must be an ISO-8601 timestamp") from exc

    @property
    def canonical_url(self) -> str:
        return _validate_public_https_url(self.url)

    @property
    def duplicate_key(self) -> str:
        return self.canonical_url

    def to_record(self) -> dict[str, str]:
        return {
            "name": self.name.strip(),
            "url": self.canonical_url,
            "category": self.category.strip().lower(),
            "terms_url": _validate_public_https_url(self.terms_url) if self.terms_url else "",
            "country_notes": self.country_notes.strip(),
            "payment_notes": self.payment_notes.strip(),
            "status": "eligible",
            "discovered_at": self.discovered_at or datetime.now(timezone.utc).isoformat(),
        }
