"""Supervised action lifecycle and append-only in-memory audit events.

This state machine records intent and approvals only. It never invokes a
platform, browser, payment API, or external code. Production persistence and
authenticated approval endpoints are intentionally separate follow-up work.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

ActionKind = Literal[
    "read_public_info",
    "prepare_draft",
    "submit_application",
    "accept_terms",
    "publish_content",
    "share_personal_data",
    "spend_money",
    "withdraw_funds",
]
RequestStatus = Literal["pending_approval", "approved", "rejected", "completed", "cancelled"]

SENSITIVE_ACTIONS = frozenset({
    "submit_application",
    "accept_terms",
    "publish_content",
    "share_personal_data",
    "spend_money",
    "withdraw_funds",
})


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class AuditEvent:
    event_id: str
    request_id: str
    event_type: str
    actor: str
    occurred_at: str
    details: str = ""


@dataclass
class SupervisedAction:
    request_id: str
    opportunity_id: int
    action: ActionKind
    description: str
    status: RequestStatus = "pending_approval"
    created_at: str = field(default_factory=_timestamp)
    approved_at: str | None = None
    completed_at: str | None = None


class SupervisionError(ValueError):
    """Raised when a supervised action transition is not permitted."""


class SupervisionQueue:
    """Small deterministic state machine; callers must persist and authorize it."""

    def __init__(self) -> None:
        self._requests: dict[str, SupervisedAction] = {}
        self._events: list[AuditEvent] = []
        self._lock = RLock()

    def _event(self, request: SupervisedAction, event_type: str, actor: str, details: str = "") -> None:
        self._events.append(AuditEvent(
            event_id=str(uuid4()),
            request_id=request.request_id,
            event_type=event_type,
            actor=actor,
            occurred_at=_timestamp(),
            details=details[:1000],
        ))

    def create(
        self,
        *,
        opportunity_id: int,
        action: ActionKind,
        description: str,
        actor: str = "system",
        opportunity_eligible: bool,
        source_approved: bool,
        evidence_fresh: bool,
    ) -> SupervisedAction:
        if isinstance(opportunity_id, bool) or not isinstance(opportunity_id, int) or opportunity_id < 1:
            raise SupervisionError("opportunity_id must be a positive integer")
        if not isinstance(action, str) or action not in {
            "read_public_info", "prepare_draft", "submit_application",
            "accept_terms", "publish_content", "share_personal_data",
            "spend_money", "withdraw_funds",
        }:
            raise SupervisionError("unsupported action")
        if not isinstance(description, str) or not description.strip():
            raise SupervisionError("action description is required")
        if not isinstance(actor, str) or not actor.strip():
            raise SupervisionError("request actor is required")
        if any(value is not True for value in (opportunity_eligible, source_approved, evidence_fresh)):
            raise SupervisionError("opportunity must be eligible, source-approved, and supported by fresh evidence")
        request = SupervisedAction(
            request_id=str(uuid4()),
            opportunity_id=opportunity_id,
            action=action,
            description=description.strip()[:500],
        )
        with self._lock:
            self._requests[request.request_id] = request
            self._event(request, "requested", actor, "Awaiting explicit user approval")
            return request

    def approve(self, request_id: str, *, actor: str) -> SupervisedAction:
        with self._lock:
            request = self._get(request_id)
            if request.status != "pending_approval":
                raise SupervisionError("only pending requests can be approved")
            if not isinstance(actor, str) or not actor.strip() or actor.strip().casefold() == "system":
                raise SupervisionError("approval must be attributed to a human actor")
            request.status = "approved"
            request.approved_at = _timestamp()
            self._event(request, "approved", actor, "Human approval recorded; no action executed")
            return request

    def reject(self, request_id: str, *, actor: str, reason: str = "") -> SupervisedAction:
        with self._lock:
            request = self._get(request_id)
            if request.status != "pending_approval":
                raise SupervisionError("only pending requests can be rejected")
            if not isinstance(actor, str) or not actor.strip() or actor.strip().casefold() == "system":
                raise SupervisionError("decision must be attributed to a human actor")
            request.status = "rejected"
            self._event(request, "rejected", actor, reason)
            return request

    def complete(self, request_id: str, *, actor: str, evidence: str) -> SupervisedAction:
        if not isinstance(actor, str) or not actor.strip() or actor.strip().casefold() == "system":
            raise SupervisionError("decision must be attributed to a human actor")
        with self._lock:
            request = self._get(request_id)
            if request.status != "approved":
                raise SupervisionError("only approved requests can be marked complete")
            if not isinstance(evidence, str) or not evidence.strip():
                raise SupervisionError("completion evidence is required")
            request.status = "completed"
            request.completed_at = _timestamp()
            self._event(request, "marked_completed", actor, evidence)
            return request

    def cancel(self, request_id: str, *, actor: str, reason: str = "") -> SupervisedAction:
        if not actor.strip() or actor.strip().casefold() == "system":
            raise SupervisionError("decision must be attributed to a human actor")
        with self._lock:
            request = self._get(request_id)
            if request.status in ("completed", "rejected", "cancelled"):
                raise SupervisionError("terminal requests cannot be cancelled")
            request.status = "cancelled"
            self._event(request, "cancelled", actor, reason)
            return request

    def get(self, request_id: str) -> SupervisedAction | None:
        with self._lock:
            return self._requests.get(request_id)

    def audit_events(self, request_id: str | None = None) -> tuple[AuditEvent, ...]:
        with self._lock:
            events = self._events
            if request_id is not None:
                events = [event for event in events if event.request_id == request_id]
            return tuple(events)

    def _get(self, request_id: str) -> SupervisedAction:
        if not isinstance(request_id, str) or not request_id.strip():
            raise SupervisionError("request_id is required")
        request = self._requests.get(request_id)
        if request is None:
            raise SupervisionError("action request not found")
        return request
