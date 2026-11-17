"""Capability-scoped discovery adapter registry.

Adapters are trusted, locally registered Python integrations. This module
never fetches arbitrary URLs, executes source-provided code, or participates
in third-party platforms. Discovery adapters return metadata with provenance.
"""
from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Literal, Protocol

from .discovery import SourceCandidate
from .opportunities import normalize_url

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
        if not self.adapter_id.strip() or not self.display_name.strip():
            raise ValueError("adapter id and display name are required")
        if not self.categories:
            raise ValueError("at least one supported category is required")
        if not self.allowed_domains:
            raise ValueError("at least one exact allowed domain is required")
        if self.requests_per_minute < 1 or self.requests_per_minute > 600:
            raise ValueError("requests_per_minute must be between 1 and 600")
        if self.execution_mode != "official_api" and self.allowed_actions:
            raise ValueError("only official_api adapters may declare platform actions")
        if self.allowed_actions and not self.terms_permit_automation:
            raise ValueError("platform actions require explicit terms permission")
        if self.allowed_actions and not self.requires_user_approval:
            raise ValueError("platform actions must retain user approval")
        for domain in self.allowed_domains:
            if (
                not domain
                or domain != domain.strip()
                or domain.startswith("*.")
                or "/" in domain
                or ":" in domain
                or "@" in domain
                or domain.casefold() != domain
            ):
                raise ValueError("allowed_domains must contain lowercase exact bare hostnames")


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

    def __post_init__(self) -> None:
        if not self.title.strip() or not self.source_name.strip():
            raise ValueError("lead title and source_name are required")
        normalize_url(self.url)
        if self.terms_url:
            normalize_url(self.terms_url)
        if not self.observed_at.strip():
            raise ValueError("observed_at timestamp is required")


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
            host = normalize_url(lead.url).split("/", 3)[2].split("@")[-1].split(":")[0].casefold()
            if allowed_hosts and host not in allowed_hosts:
                raise ValueError("lead URL host is outside the adapter domain allowlist")
            validated.append(lead)
        return validated


def source_candidate_from_lead(lead: DiscoveredLead) -> SourceCandidate:
    """Convert a lead to pending source metadata; never auto-approve it."""
    return SourceCandidate(
        name=lead.source_name,
        url=lead.url,
        category=lead.category,
        terms_url=lead.terms_url or None,
        country_notes="",
        payment_notes=lead.summary,
        status="pending",
        discovered_at=lead.observed_at,
    )
