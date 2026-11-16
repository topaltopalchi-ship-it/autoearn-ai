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
    region_fit: int = 0
    effort_fit: int = 0

    def __post_init__(self) -> None:
        if not self.title.strip():
            raise ValueError("title is required")
        normalize_url(self.url)
        for field in ("reward_clarity", "terms_clarity", "source_trust", "region_fit", "effort_fit"):
            value = getattr(self, field)
            if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 100:
                raise ValueError(f"{field} must be an integer from 0 to 100")


def score_opportunity(opportunity: Opportunity) -> dict[str, object]:
    """Return a transparent weighted score and reasons for the supplied metadata."""
    weights = {
        "reward_clarity": 0.25,
        "terms_clarity": 0.25,
        "source_trust": 0.30,
        "region_fit": 0.10,
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


# Provider-agnostic discovery primitives. Search adapters supply metadata; this
# module never fetches arbitrary destination URLs or performs platform activity.
import ipaddress
import re
from datetime import datetime, timezone
from typing import Iterable, Protocol
from urllib.parse import urlsplit


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    snippet: str = ""
    provider: str = "unspecified"


class SearchProvider(Protocol):
    def search(self, query: str, limit: int = 10) -> Iterable[SearchResult | dict]:
        """Return search results without visiting their destination pages."""
        ...


@dataclass(frozen=True)
class DiscoveredOpportunity:
    title: str
    url: str
    snippet: str
    provider: str
    domain: str
    discovered_at: str
    confidence: int
    signals: tuple[str, ...]
    review_required: bool = True


_REWARD_TERMS = re.compile(
    r"\b(rewards?|earn|cashback|points|prize|payout|gift card|bounty|incentive)\b", re.I
)
_TERMS_TERMS = re.compile(r"\b(terms|conditions|eligibility|rules|policy)\b", re.I)
_ELIGIBILITY_TERMS = re.compile(
    r"\b(eligible|eligibility|region|country|residents|age\s+\d+)\b", re.I
)


def _is_public_host(host: str) -> bool:
    host = host.strip("[]").lower().rstrip(".")
    if host == "localhost" or host.endswith(".localhost"):
        return False
    try:
        return ipaddress.ip_address(host).is_global
    except ValueError:
        return True


def _coerce_search_result(value: SearchResult | dict) -> SearchResult:
    if isinstance(value, SearchResult):
        item = value
    elif isinstance(value, dict):
        item = SearchResult(
            title=str(value.get("title", "")).strip(),
            url=str(value.get("url", "")).strip(),
            snippet=str(value.get("snippet", "")).strip(),
            provider=str(value.get("provider", "unspecified")).strip() or "unspecified",
        )
    else:
        raise ValueError("unsupported search result")
    if not item.title or len(item.title) > 300:
        raise ValueError("search result title must contain 1 to 300 characters")
    if len(item.snippet) > 2000 or len(item.provider) > 100:
        raise ValueError("search result metadata is too long")
    canonical = normalize_url(item.url)
    host = urlsplit(canonical).hostname or ""
    if not _is_public_host(host):
        raise ValueError("local and private network URLs are not accepted")
    return SearchResult(item.title, canonical, item.snippet, item.provider)


def analyze_search_result(item: SearchResult) -> DiscoveredOpportunity:
    """Extract weak textual signals; they are not proof of legitimacy."""
    parsed = urlsplit(item.url)
    text = item.title + " " + item.snippet
    signals = []
    if parsed.scheme == "https":
        signals.append("https_transport")
    if _TERMS_TERMS.search(text):
        signals.append("terms_or_rules_mentioned")
    if _REWARD_TERMS.search(text):
        signals.append("reward_language_found")
    if _ELIGIBILITY_TERMS.search(text):
        signals.append("eligibility_language_found")
    return DiscoveredOpportunity(
        title=item.title,
        url=item.url,
        snippet=item.snippet,
        provider=item.provider,
        domain=(parsed.hostname or "").lower(),
        discovered_at=datetime.now(timezone.utc).isoformat(),
        confidence=min(100, 15 + 15 * len(signals)),
        signals=tuple(signals),
    )


def discover_opportunities(
    query: str, provider: SearchProvider, limit: int = 10
) -> list[DiscoveredOpportunity]:
    """Validate, canonicalize, deduplicate and triage a provider result batch."""
    cleaned = " ".join(query.split()) if isinstance(query, str) else ""
    if not cleaned or len(cleaned) > 300:
        raise ValueError("query must contain 1 to 300 characters")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 50:
        raise ValueError("limit must be an integer from 1 to 50")

    output = []
    seen = set()
    for raw in provider.search(cleaned, limit=limit):
        try:
            item = _coerce_search_result(raw)
        except (TypeError, ValueError):
            # Isolate malformed rows; retain valid results from the same batch.
            continue
        if item.url in seen:
            continue
        seen.add(item.url)
        output.append(analyze_search_result(item))
        if len(output) == limit:
            break
    return output
