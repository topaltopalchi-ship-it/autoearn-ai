"""Capability-scoped discovery adapter registry.

Adapters are trusted, locally registered Python integrations. This module
never fetches arbitrary URLs, executes source-provided code, or participates
in third-party platforms. Discovery adapters return metadata with provenance.
"""
from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Literal, Protocol
from urllib.parse import urlsplit
import re

from .discovery import SourceCandidate
from .opportunities import normalize_url
from .tracks import get_track, infer_track_from_text, track_matches_category, tracks_for_category

Category = Literal[
    "games_competitions",
    "surveys_microtasks",
    "freelancing_services",
    "ai_content_products",
    "other",
]
ExecutionMode = Literal["manual", "assist", "official_api"]


@dataclass(frozen=True)
class AdapterManifest:
    adapter_id: str
    display_name: str
    categories: tuple[Category, ...]
    execution_mode: ExecutionMode = "manual"
    allowed_domains: tuple[str, ...] = ()
    allowed_actions: tuple[str, ...] = ()
    requests_per_minute: int = 10
    terms_permit_automation: bool = False
    requires_user_approval: bool = True

    def __post_init__(self) -> None:
        if (
            not isinstance(self.adapter_id, str)
            or not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", self.adapter_id)
            or not isinstance(self.display_name, str)
            or not self.display_name.strip()
            or len(self.display_name) > 120
        ):
            raise ValueError("adapter id and display name must be valid")
        valid_categories = {
            "games_competitions",
            "surveys_microtasks",
            "freelancing_services",
            "ai_content_products",
            "other",
        }
        if (
            not isinstance(self.categories, tuple)
            or not self.categories
            or any(not isinstance(category, str) or category not in valid_categories for category in self.categories)
        ):
            raise ValueError("categories must be a non-empty tuple of supported categories")
        if len(set(self.categories)) != len(self.categories):
            raise ValueError("categories must not contain duplicates")
        if not isinstance(self.execution_mode, str) or self.execution_mode not in {"manual", "assist", "official_api"}:
            raise ValueError("execution_mode is not supported")
        if (
            not isinstance(self.allowed_domains, tuple)
            or not self.allowed_domains
            or any(not isinstance(domain, str) for domain in self.allowed_domains)
        ):
            raise ValueError("allowed_domains must be a non-empty tuple of hostnames")
        if not isinstance(self.allowed_actions, tuple) or any(
            not isinstance(action, str)
            or not re.fullmatch(r"[a-z][a-z0-9_]{0,39}", action)
            for action in self.allowed_actions
        ):
            raise ValueError("allowed_actions must use safe lowercase action identifiers")
        if len(set(self.allowed_actions)) != len(self.allowed_actions):
            raise ValueError("allowed_actions must not contain duplicates")
        if (
            isinstance(self.requests_per_minute, bool)
            or not isinstance(self.requests_per_minute, int)
            or not 1 <= self.requests_per_minute <= 600
        ):
            raise ValueError("requests_per_minute must be an integer between 1 and 600")
        if not isinstance(self.terms_permit_automation, bool) or not isinstance(self.requires_user_approval, bool):
            raise ValueError("automation permission and approval flags must be booleans")
        if self.execution_mode != "official_api" and self.allowed_actions:
            raise ValueError("only official_api adapters may declare platform actions")
        if self.allowed_actions and not self.terms_permit_automation:
            raise ValueError("platform actions require explicit terms permission")
        if self.allowed_actions and not self.requires_user_approval:
            raise ValueError("platform actions must retain user approval")
        for domain in self.allowed_domains:
            labels = domain.split(".")
            valid_labels = all(
                re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
                for label in labels
            )
            if (
                not domain
                or domain != domain.strip()
                or domain.casefold() != domain
                or len(domain) > 253
                or len(labels) < 2
                or not valid_labels
            ):
                raise ValueError("allowed_domains must contain lowercase exact public hostnames")


@dataclass(frozen=True)
class DiscoveredLead:
    title: str
    url: str
    category: Category
    source_name: str
    observed_at: str
    summary: str = ""
    terms_url: str = ""
    evidence: tuple[str, ...] = ()
    track_key: str = ""

    def __post_init__(self) -> None:
        if not self.title.strip() or not self.source_name.strip():
            raise ValueError("lead title and source_name are required")
        for field_name, value in (("lead", self.url), ("terms", self.terms_url)):
            if not value and field_name == "terms":
                continue
            normalize_url(value)
            parsed = urlsplit(value.strip())
            if parsed.scheme.casefold() != "https" or parsed.port not in (None, 443):
                raise ValueError(f"{field_name} URL must use HTTPS on the standard port")
            if parsed.fragment:
                raise ValueError(f"{field_name} URL must not contain a fragment")
        if not self.observed_at.strip():
            raise ValueError("observed_at timestamp is required")
        if self.track_key and not track_matches_category(self.track_key, self.category):
            raise ValueError("track_key must match the lead category")


class DiscoveryAdapter(Protocol):
    @property
    def manifest(self) -> AdapterManifest: ...

    def discover(self) -> list[DiscoveredLead]: ...


class AdapterRegistry:
    """Thread-safe registry; only explicitly registered adapters can run."""

    def __init__(self) -> None:
        self._adapters: dict[str, DiscoveryAdapter] = {}
        self._lock = RLock()

    def register(self, adapter: DiscoveryAdapter) -> None:
        manifest = adapter.manifest
        if not isinstance(manifest, AdapterManifest):
            raise TypeError("adapter must expose an AdapterManifest")
        with self._lock:
            if manifest.adapter_id in self._adapters:
                raise ValueError("adapter id is already registered")
            self._adapters[manifest.adapter_id] = adapter

    def get_manifest(self, adapter_id: str) -> AdapterManifest | None:
        with self._lock:
            adapter = self._adapters.get(adapter_id)
            return adapter.manifest if adapter else None

    def list_manifests(self) -> list[AdapterManifest]:
        with self._lock:
            manifests = [adapter.manifest for adapter in self._adapters.values()]
        return sorted(manifests, key=lambda item: item.adapter_id)

    def discover(self, adapter_id: str) -> list[DiscoveredLead]:
        with self._lock:
            adapter = self._adapters.get(adapter_id)
        if adapter is None:
            raise KeyError("adapter is not registered")

        manifest = adapter.manifest
        leads = adapter.discover()
        if not isinstance(leads, list):
            raise TypeError("adapter discover() must return a list")
        validated: list[DiscoveredLead] = []
        allowed_hosts = {host.casefold() for host in manifest.allowed_domains}
        for lead in leads:
            if not isinstance(lead, DiscoveredLead):
                raise TypeError("adapter returned an invalid lead")
            if lead.category not in manifest.categories:
                raise ValueError("adapter returned a lead outside its declared categories")
            parsed = urlsplit(normalize_url(lead.url))
            host = (parsed.hostname or "").casefold()
            if parsed.username is not None or parsed.password is not None:
                raise ValueError("lead URL must not contain embedded credentials")
            if host not in allowed_hosts:
                raise ValueError("lead URL host is outside the adapter domain allowlist")
            validated.append(lead)
        return validated


def source_candidate_from_lead(lead: DiscoveredLead) -> SourceCandidate:
    """Convert a lead to pending source metadata; never auto-approve it."""
    inferred_track = lead.track_key or infer_track_from_text(lead.title, lead.summary, lead.category)
    return SourceCandidate(
        name=lead.source_name,
        url=lead.url,
        category=lead.category,
        terms_url=lead.terms_url or None,
        country_notes="",
        payment_notes=lead.summary,
        status="pending",
        discovered_at=lead.observed_at,
        track_key=inferred_track,
        track_review_status="matched" if inferred_track else "needs_review",
    )
