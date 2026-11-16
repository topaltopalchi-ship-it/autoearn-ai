"""Safe intake records for manually supplied public opportunity sources.

This module stores candidate metadata only. It does not fetch pages, bypass
access controls, or perform platform actions.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

from .opportunities import normalize_url

ReviewStatus = Literal["pending", "approved", "rejected"]


@dataclass(frozen=True)
class SourceCandidate:
    name: str
    url: str
    category: str = "game_rewards"
    terms_url: str | None = None
    country_notes: str = ""
    payment_notes: str = ""
    status: ReviewStatus = "pending"
    discovered_at: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("source name is required")
        normalize_url(self.url)
        if self.terms_url:
            normalize_url(self.terms_url)
        if not isinstance(self.category, str) or not self.category.strip():
            raise ValueError("category is required")
        if self.status not in ("pending", "approved", "rejected"):
            raise ValueError("status must be pending, approved, or rejected")
        if self.discovered_at:
            try:
                datetime.fromisoformat(self.discovered_at.replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValueError("discovered_at must be an ISO-8601 timestamp") from exc

    @property
    def canonical_url(self) -> str:
        return normalize_url(self.url)

    @property
    def duplicate_key(self) -> str:
        return self.canonical_url

    def to_record(self) -> dict[str, str]:
        return {
            "name": self.name.strip(),
            "url": self.canonical_url,
            "category": self.category.strip().lower(),
            "terms_url": normalize_url(self.terms_url) if self.terms_url else "",
            "country_notes": self.country_notes.strip(),
            "payment_notes": self.payment_notes.strip(),
            "status": self.status,
            "discovered_at": self.discovered_at or datetime.now(timezone.utc).isoformat(),
        }
