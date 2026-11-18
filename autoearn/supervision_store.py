"""SQLite-backed supervised action queue with append-only audit events.

This persistence layer records requests and human decisions only. It never
executes platform actions. Applications must enforce authentication and
authorization before exposing approve/reject operations over HTTP.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any
from uuid import uuid4

from .supervision import (
    ActionKind, AuditEvent, RequestStatus, SupervisedAction, SupervisionError,
    _timestamp,
)

_ALLOWED_ACTIONS = {
    "read_public_info", "prepare_draft", "submit_application", "accept_terms",
    "publish_content", "share_personal_data", "spend_money", "withdraw_funds",
}
_TERMINAL = {"rejected", "completed", "cancelled"}


class SQLiteSupervisionStore:
    def __init__(self, database: str | Path):
        self.database = str(database)
        self.initialize()

    def _connect(self):
        db = sqlite3.connect(self.database, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        return db

    def initialize(self) -> None:
        Path(self.database).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS supervised_actions (
                request_id TEXT PRIMARY KEY,
                opportunity_id INTEGER NOT NULL CHECK(opportunity_id > 0),
                action TEXT NOT NULL,
                description TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending_approval',
                created_at TEXT NOT NULL,
                approved_at TEXT,
                completed_at TEXT
            );
            CREATE TABLE IF NOT EXISTS supervision_audit (
                event_id TEXT PRIMARY KEY,
                request_id TEXT NOT NULL REFERENCES supervised_actions(request_id),
                event_type TEXT NOT NULL,
                actor TEXT NOT NULL,
                occurred_at TEXT NOT NULL,
                details TEXT NOT NULL DEFAULT ''
            );
            CREATE INDEX IF NOT EXISTS idx_supervision_audit_request
                ON supervision_audit(request_id, occurred_at);
            """)

    @staticmethod
    def _action(row: sqlite3.Row) -> SupervisedAction:
        return SupervisedAction(**dict(row))

    def _event(self, db: sqlite3.Connection, request_id: str, event_type: str,
               actor: str, details: str = "") -> None:
        db.execute(
            """INSERT INTO supervision_audit
               (event_id, request_id, event_type, actor, occurred_at, details)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (str(uuid4()), request_id, event_type, actor.strip()[:120],
             _timestamp(), details.strip()[:1000]),
        )

    def create(self, *, opportunity_id: int, action: ActionKind, description: str,
               opportunity_eligible: bool, source_approved: bool,
               evidence_fresh: bool, actor: str = "system") -> SupervisedAction:
        if isinstance(opportunity_id, bool) or not isinstance(opportunity_id, int) or opportunity_id < 1:
            raise SupervisionError("opportunity_id must be a positive integer")
        if not isinstance(action, str) or action not in _ALLOWED_ACTIONS:
            raise SupervisionError("unsupported action")
        if not isinstance(description, str) or not description.strip():
            raise SupervisionError("action description is required")
        if not isinstance(actor, str) or not actor.strip():
            raise SupervisionError("request actor is required")
        if opportunity_eligible is not True or source_approved is not True or evidence_fresh is not True:
            raise SupervisionError(
                "opportunity must be eligible, source-approved, and supported by fresh evidence"
            )
        request = SupervisedAction(
            request_id=str(uuid4()), opportunity_id=opportunity_id,
            action=action, description=description.strip()[:500],
        )
        with self._connect() as db:
            db.execute(
                """INSERT INTO supervised_actions
                   (request_id, opportunity_id, action, description, status, created_at)
                   VALUES (?, ?, ?, ?, 'pending_approval', ?)""",
                (request.request_id, opportunity_id, action, request.description, request.created_at),
            )
            self._event(db, request.request_id, "requested", actor, "Awaiting explicit user approval")
        return request

    def _transition(self, request_id: str, allowed: set[str], new_status: str,
                    event_type: str, actor: str, details: str = "") -> SupervisedAction:
        if not isinstance(request_id, str) or not request_id.strip():
            raise SupervisionError("request_id is required")
        if not isinstance(actor, str) or not actor.strip() or actor.strip().casefold() == "system":
            raise SupervisionError("decision must be attributed to a human actor")
        if not isinstance(details, str):
            raise SupervisionError("decision details must be text")
        with self._connect() as db:
            # Serialize transitions before reading status so competing decisions
            # cannot both observe the same pre-transition state.
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM supervised_actions WHERE request_id=?", (request_id,)
            ).fetchone()
            if row is None:
                raise SupervisionError("action request not found")
            if row["status"] not in allowed:
                raise SupervisionError(f"request cannot transition from {row['status']}")
            stamp = _timestamp()
            approved_at = stamp if new_status == "approved" else row["approved_at"]
            completed_at = stamp if new_status == "completed" else row["completed_at"]
            db.execute(
                """UPDATE supervised_actions SET status=?, approved_at=?, completed_at=?
                   WHERE request_id=?""",
                (new_status, approved_at, completed_at, request_id),
            )
            self._event(db, request_id, event_type, actor, details)
            updated = db.execute(
                "SELECT * FROM supervised_actions WHERE request_id=?", (request_id,)
            ).fetchone()
            return self._action(updated)

    def approve(self, request_id: str, *, actor: str) -> SupervisedAction:
        return self._transition(request_id, {"pending_approval"}, "approved", "approved",
                                actor, "Human approval recorded; no action executed")

    def reject(self, request_id: str, *, actor: str, reason: str = "") -> SupervisedAction:
        if not isinstance(reason, str):
            raise SupervisionError("rejection reason must be text")
        return self._transition(request_id, {"pending_approval"}, "rejected", "rejected", actor, reason)

    def complete(self, request_id: str, *, actor: str, evidence: str) -> SupervisedAction:
        if not isinstance(evidence, str) or not evidence.strip():
            raise SupervisionError("completion evidence is required")
        return self._transition(request_id, {"approved"}, "completed", "marked_completed", actor, evidence)

    def cancel(self, request_id: str, *, actor: str, reason: str = "") -> SupervisedAction:
        if not isinstance(reason, str):
            raise SupervisionError("cancellation reason must be text")
        return self._transition(request_id, {"pending_approval", "approved"}, "cancelled",
                                "cancelled", actor, reason)

    def get(self, request_id: str) -> SupervisedAction | None:
        with self._connect() as db:
            row = db.execute(
                "SELECT * FROM supervised_actions WHERE request_id=?", (request_id,)
            ).fetchone()
            return self._action(row) if row else None

    def list(self, status: RequestStatus | None = None) -> list[SupervisedAction]:
        valid_statuses = {"pending_approval", "approved", "rejected", "completed", "cancelled"}
        if status is not None and (not isinstance(status, str) or status not in valid_statuses):
            raise SupervisionError("unsupported request status filter")
        with self._connect() as db:
            if status:
                rows = db.execute(
                    "SELECT * FROM supervised_actions WHERE status=? ORDER BY created_at DESC",
                    (status,),
                ).fetchall()
            else:
                rows = db.execute(
                    "SELECT * FROM supervised_actions ORDER BY created_at DESC"
                ).fetchall()
            return [self._action(row) for row in rows]

    def audit_events(self, request_id: str | None = None) -> tuple[AuditEvent, ...]:
        with self._connect() as db:
            if request_id:
                rows = db.execute(
                    "SELECT * FROM supervision_audit WHERE request_id=? ORDER BY rowid",
                    (request_id,),
                ).fetchall()
            else:
                rows = db.execute(
                    "SELECT * FROM supervision_audit ORDER BY rowid"
                ).fetchall()
            return tuple(AuditEvent(**dict(row)) for row in rows)
