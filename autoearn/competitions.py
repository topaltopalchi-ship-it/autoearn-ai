"""Competition-agent planning and tightly gated execution contracts.

The built-in planner is deterministic and transparent. Real submissions require
a locally registered official-API adapter whose manifest explicitly permits
automated agents; this module never drives browsers, bypasses anti-cheat, or
executes competition-provided code.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol
from urllib.parse import urlsplit

Eligibility = Literal["eligible", "ineligible", "unknown"]
TaskType = Literal["logic", "coding", "chess", "strategy", "general"]


@dataclass(frozen=True)
class Competition:
    competition_id: int
    title: str
    url: str
    rules_url: str
    task_type: TaskType
    country: str
    eligibility: Eligibility
    terms_verified: bool
    automated_agents_allowed: bool
    official_api: bool
    allowed_actions: tuple[str, ...] = ()


@dataclass(frozen=True)
class Readiness:
    ready: bool
    blockers: tuple[str, ...]


def assess_competition(item: Competition) -> Readiness:
    blockers: list[str] = []
    if item.eligibility != "eligible":
        blockers.append("country eligibility is not confirmed")
    if not item.terms_verified:
        blockers.append("competition rules have not been manually verified")
    if not item.automated_agents_allowed:
        blockers.append("competition rules do not explicitly permit automated agents")
    if not item.official_api:
        blockers.append("an official competition API is not available")
    if "submit_entry" not in item.allowed_actions:
        blockers.append("adapter does not declare the submit_entry capability")
    parsed = urlsplit(item.url)
    if parsed.scheme != "https" or not parsed.hostname:
        blockers.append("competition URL must use HTTPS")
    if item.rules_url:
        rules = urlsplit(item.rules_url)
        if rules.scheme != "https" or not rules.hostname:
            blockers.append("rules URL must use HTTPS")
    return Readiness(ready=not blockers, blockers=tuple(blockers))


@dataclass(frozen=True)
class AgentStrategy:
    competition_id: int
    task_type: TaskType
    provider: str
    approach: str
    steps: tuple[str, ...]
    validation_checks: tuple[str, ...]
    fallback: str
    confidence: int


_STRATEGIES: dict[TaskType, tuple[str, tuple[str, ...], tuple[str, ...], str, int]] = {
    "logic": (
        "Constraint-first reasoning with independent verification",
        ("Parse the prompt and list all explicit constraints",
         "Represent unknowns and candidate states separately",
         "Solve using the smallest consistent set of assumptions",
         "Check every constraint against the proposed answer",
         "Re-derive the answer using a second reasoning path"),
        ("No constraint is silently dropped",
         "A second derivation reaches the same result",
         "The final response matches the required answer format"),
        "Return an uncertainty report rather than guessing", 68,
    ),
    "coding": (
        "Test-driven implementation with edge-case review",
        ("Extract input, output, limits, and edge cases",
         "Choose an algorithm and estimate time and memory complexity",
         "Create a minimal correct solution",
         "Test boundary, empty, malformed, and maximum-size cases",
         "Review complexity and remove nondeterministic behavior"),
        ("Examples pass",
         "Boundary tests pass",
         "Complexity fits the published limits",
         "No hidden network, filesystem, or credential access"),
        "Keep the last verified solution and report unresolved tests", 65,
    ),
    "chess": (
        "Legal-move search with tactical safety checks",
        ("Parse the position and legal-move constraints",
         "Generate only legal candidate moves through an approved chess engine",
         "Check immediate checks, captures, and threats",
         "Compare candidate continuations at a fixed search budget",
         "Verify the selected move remains legal"),
        ("Move is legal in the current position",
         "No immediate forced loss is overlooked",
         "Search budget and clock limits are respected"),
        "Choose a verified legal move or abstain", 58,
    ),
    "strategy": (
        "Objective-driven planning with risk-adjusted alternatives",
        ("Identify the win condition and scoring rules",
         "List available actions and their known costs",
         "Estimate outcomes under conservative assumptions",
         "Compare the best action with a safe fallback",
         "Re-evaluate after each permitted state update"),
        ("Every action is permitted by the rules",
         "Resource and time limits are respected",
         "The plan has a defined stop condition"),
        "Choose the lowest-risk legal action or abstain", 60,
    ),
    "general": (
        "Structured problem decomposition and evidence checking",
        ("Restate the objective and output format",
         "Separate known facts from assumptions",
         "Solve the problem in small verifiable steps",
         "Check the result against the published rubric",
         "Prepare a concise final response"),
        ("All required fields are present",
         "Claims are supported by the prompt or evidence",
         "Output format matches the competition requirements"),
        "Flag ambiguity and request human review", 50,
    ),
}


def build_strategy(
    competition_id: int,
    task_type: TaskType,
    objective: str = "",
) -> AgentStrategy:
    if competition_id < 1:
        raise ValueError("competition_id must be positive")
    if task_type not in _STRATEGIES:
        raise ValueError("unsupported competition task type")
    if len(objective) > 1000:
        raise ValueError("objective is too long")
    approach, steps, checks, fallback, confidence = _STRATEGIES[task_type]
    if objective.strip():
        approach = f"{approach}. Objective: {objective.strip()[:240]}"
    return AgentStrategy(
        competition_id=competition_id,
        task_type=task_type,
        provider="heuristic-baseline",
        approach=approach,
        steps=steps,
        validation_checks=checks,
        fallback=fallback,
        confidence=confidence,
    )


@dataclass(frozen=True)
class CompetitionAdapterManifest:
    adapter_id: str
    exact_host: str
    official_api: bool
    automated_agents_allowed: bool
    allowed_actions: tuple[str, ...]
    requests_per_minute: int = 10

    def __post_init__(self) -> None:
        if not self.adapter_id.strip() or not self.exact_host.strip():
            raise ValueError("adapter id and exact host are required")
        if self.exact_host != self.exact_host.casefold() or "*" in self.exact_host:
            raise ValueError("adapter host must be an exact lowercase hostname")
        if not self.official_api or not self.automated_agents_allowed:
            raise ValueError("competition adapters require an official API and explicit agent permission")
        if "submit_entry" not in self.allowed_actions:
            raise ValueError("adapter must explicitly declare submit_entry")
        if not 1 <= self.requests_per_minute <= 60:
            raise ValueError("requests_per_minute must be between 1 and 60")


@dataclass(frozen=True)
class SubmissionReceipt:
    external_entry_id: str
    status: str
    evidence: str = ""


class CompetitionAdapter(Protocol):
    @property
    def manifest(self) -> CompetitionAdapterManifest: ...

    def submit_entry(self, competition: Competition, payload: dict) -> SubmissionReceipt: ...


class CompetitionAdapterRegistry:
    """Only trusted, locally registered official-API adapters can submit."""

    def __init__(self) -> None:
        self._adapters: dict[str, CompetitionAdapter] = {}

    def get_manifest(self, adapter_id: str) -> CompetitionAdapterManifest | None:
        adapter = self._adapters.get(adapter_id)
        return adapter.manifest if adapter else None

    def register(self, adapter: CompetitionAdapter) -> None:
        manifest = adapter.manifest
        if not isinstance(manifest, CompetitionAdapterManifest):
            raise TypeError("adapter must expose a CompetitionAdapterManifest")
        if manifest.adapter_id in self._adapters:
            raise ValueError("adapter id is already registered")
        self._adapters[manifest.adapter_id] = adapter

    def submit(
        self,
        adapter_id: str,
        competition: Competition,
        payload: dict,
        *,
        owner_confirmed: bool,
    ) -> SubmissionReceipt:
        if not owner_confirmed:
            raise PermissionError("explicit owner confirmation is required")
        readiness = assess_competition(competition)
        if not readiness.ready:
            raise PermissionError("; ".join(readiness.blockers))
        adapter = self._adapters.get(adapter_id)
        if adapter is None:
            raise KeyError("official competition adapter is not registered")
        manifest = adapter.manifest
        host = (urlsplit(competition.url).hostname or "").casefold()
        if host != manifest.exact_host:
            raise PermissionError("competition host is outside the adapter's exact allowlist")
        if "submit_entry" not in manifest.allowed_actions:
            raise PermissionError("adapter is not allowed to submit entries")
        if not isinstance(payload, dict) or len(str(payload)) > 20000:
            raise ValueError("entry payload must be a bounded object")
        receipt = adapter.submit_entry(competition, payload)
        if not isinstance(receipt, SubmissionReceipt) or not receipt.external_entry_id.strip():
            raise RuntimeError("adapter returned an invalid submission receipt")
        return receipt
