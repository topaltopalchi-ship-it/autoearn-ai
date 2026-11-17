"""Conservative task suitability screening for AI assistance.

This module classifies task characteristics only. It does not decide platform
policy, complete work, submit entries, or authorize autonomous execution.
Unknown AI-use permission always requires human review.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

AIPermission = Literal["allowed", "prohibited", "unknown"]
Suitability = Literal[
    "blocked",
    "human_only",
    "manual_policy_review",
    "ai_assisted_human_review",
    "ai_draft_candidate",
]


@dataclass(frozen=True)
class TaskProfile:
    title: str
    ai_permission: AIPermission = "unknown"
    requires_physical_presence: bool = False
    requires_personal_experience: bool = False
    requires_identity_attestation: bool = False
    requires_captcha: bool = False
    requires_live_human_interaction: bool = False
    contains_sensitive_personal_data: bool = False
    repetitive_information_processing: bool = False
    output_is_objectively_verifiable: bool = False
    human_signoff_required: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.title, str) or not self.title.strip():
            raise ValueError("task title is required")
        if self.ai_permission not in ("allowed", "prohibited", "unknown"):
            raise ValueError("ai_permission must be allowed, prohibited, or unknown")
        for field_name in (
            "requires_physical_presence",
            "requires_personal_experience",
            "requires_identity_attestation",
            "requires_captcha",
            "requires_live_human_interaction",
            "contains_sensitive_personal_data",
            "repetitive_information_processing",
            "output_is_objectively_verifiable",
            "human_signoff_required",
        ):
            if not isinstance(getattr(self, field_name), bool):
                raise ValueError(f"{field_name} must be a boolean")


@dataclass(frozen=True)
class SuitabilityAssessment:
    suitability: Suitability
    score: int
    reasons: tuple[str, ...]
    permitted_ai_role: str
    execution_authorized: bool = False


def assess_task_suitability(profile: TaskProfile) -> SuitabilityAssessment:
    """Classify whether AI may assist; never authorize platform execution."""
    reasons: list[str] = []

    if profile.ai_permission == "prohibited":
        return SuitabilityAssessment(
            "blocked", 0,
            ("platform or task rules prohibit AI assistance",),
            "Do not use AI for this task.",
        )

    human_only_flags = (
        (profile.requires_physical_presence, "task requires physical presence"),
        (profile.requires_personal_experience, "task depends on the worker's genuine personal experience"),
        (profile.requires_identity_attestation, "task requires a truthful personal attestation"),
        (profile.requires_captcha, "task includes a human-verification challenge"),
        (profile.requires_live_human_interaction, "task requires live human interaction"),
    )
    for active, reason in human_only_flags:
        if active:
            reasons.append(reason)

    if reasons:
        return SuitabilityAssessment(
            "human_only", 0, tuple(reasons),
            "A human must perform the required activity; do not simulate or outsource identity.",
        )

    if profile.ai_permission == "unknown":
        return SuitabilityAssessment(
            "manual_policy_review", 0,
            ("permission to use AI is not explicitly documented",),
            "Ask the platform or task owner for permission; do not use AI until confirmed.",
        )

    if profile.contains_sensitive_personal_data:
        return SuitabilityAssessment(
            "ai_assisted_human_review", 25,
            ("task contains sensitive personal data; privacy and data-processing permission need review",),
            "Do not send sensitive data to an AI provider; use only an approved privacy-preserving workflow.",
        )

    score = 30
    if profile.repetitive_information_processing:
        score += 30
        reasons.append("task includes repetitive information processing")
    if profile.output_is_objectively_verifiable:
        score += 25
        reasons.append("output can be checked against objective criteria")
    if profile.human_signoff_required:
        reasons.append("human sign-off remains required before delivery or submission")
    else:
        reasons.append("AI may prepare a draft, but this assessment does not authorize autonomous submission")

    if profile.repetitive_information_processing and profile.output_is_objectively_verifiable:
        suitability: Suitability = "ai_draft_candidate"
        role = "AI may prepare a bounded draft for validation; a human reviews and submits it."
    else:
        suitability = "ai_assisted_human_review"
        role = "AI may assist with preparation only; a human must verify the result and perform the task."

    return SuitabilityAssessment(
        suitability=suitability,
        score=min(85, score),
        reasons=tuple(reasons),
        permitted_ai_role=role,
        execution_authorized=False,
    )
