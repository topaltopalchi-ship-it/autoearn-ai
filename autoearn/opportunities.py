"""Safe opportunity validation, URL canonicalization, and explainable scoring.

This module deliberately does not browse websites or automate platform activity.
It scores user-supplied/publicly collected opportunity metadata only.
"""
from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


TRACKING_KEYS = {"fbclid", "gclid", "mc_cid", "mc_eid"}
TRACKING_PREFIXES = ("utm_",)


def normalize_url(url: str) -> str:
    """Return a canonical HTTP(S) URL suitable for duplicate detection."""
    if not isinstance(url, str) or not url.strip():
        raise ValueError("url must be a non-empty string")
    parsed = urlsplit(url.strip())
    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("only absolute http/https URLs are allowed")
    if parsed.username or parsed.password:
        raise ValueError("URLs containing credentials are not allowed")
    host = parsed.hostname.lower()
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    port = parsed.port
    netloc = host
    if port and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
        netloc = f"{host}:{port}"
    path = parsed.path.rstrip("/") or "/"
    query = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key.lower() not in TRACKING_KEYS
        and not key.lower().startswith(TRACKING_PREFIXES)
    ]
    query.sort()
    return urlunsplit((scheme, netloc, path, urlencode(query, doseq=True), ""))


@dataclass(frozen=True)
class Opportunity:
    """User-reviewed opportunity metadata; scores are estimates, not guarantees."""

    title: str
    url: str
    reward_clarity: int = 0
    terms_clarity: int = 0
    source_trust: int = 0
    effort_fit: int = 0

    def __post_init__(self) -> None:
        if not self.title.strip():
            raise ValueError("title is required")
        normalize_url(self.url)
        for field in ("reward_clarity", "terms_clarity", "source_trust", "effort_fit"):
            value = getattr(self, field)
            if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 100:
                raise ValueError(f"{field} must be an integer from 0 to 100")


def score_opportunity(opportunity: Opportunity) -> dict[str, object]:
    """Return a transparent weighted score and reasons for the supplied metadata."""
    weights = {
        "reward_clarity": 0.28,
        "terms_clarity": 0.28,
        "source_trust": 0.34,
        "effort_fit": 0.10,
    }
    values = {name: getattr(opportunity, name) for name in weights}
    score = round(sum(values[name] * weight for name, weight in weights.items()))
    reasons = [
        f"{name.replace('_', ' ')}: {value}/100"
        for name, value in values.items()
    ]
    risk = "low" if score >= 75 else "medium" if score >= 50 else "high"
    return {
        "score": score,
        "risk": risk,
        "reasons": reasons,
        "disclaimer": "Estimate based only on supplied metadata; verify platform terms and eligibility yourself.",
    }
