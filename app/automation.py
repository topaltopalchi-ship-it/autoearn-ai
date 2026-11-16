"""Guarded automation orchestration.

This module plans and audits work. It deliberately does not browse third-party
sites, click ads, play games, submit entries, create accounts, or request payouts.
"""
from __future__ import annotations

import json
from typing import Literal

from fastapi import APIRouter, HTTPException

from app.main import connect, now

router = APIRouter(prefix="/api/automation", tags=["automation"])

ACTION_DESCRIPTIONS = {
    "refresh_local_assessment": "Re-evaluate the saved policy and eligibility metadata locally.",
    "prepare_human_review": "Prepare a checklist for a person to verify site terms, eligibility, and payout conditions.",
    "prepare_manual_participation": "Prepare a handoff for the user to participate personally if the site permits it.",
}


def ensure_tables() -> None:
    with connect() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS automation_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            opportunity_id INTEGER NOT NULL REFERENCES opportunities(id) ON DELETE CASCADE,
            mode TEXT NOT NULL DEFAULT 'guarded_autonomy',
            status TEXT NOT NULL DEFAULT 'planned',
            policy_snapshot TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS automation_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL REFERENCES automation_runs(id) ON DELETE CASCADE,
            opportunity_id INTEGER NOT NULL REFERENCES opportunities(id) ON DELETE CASCADE,
            action_type TEXT NOT NULL,
            description TEXT NOT NULL,
            status TEXT NOT NULL,
            result TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """)


def action_dict(row):
    item = dict(row)
    try:
        item["result"] = json.loads(item["result"]) if item["result"] else None
    except (TypeError, ValueError):
        item["result"] = None
    return item


@router.post("/opportunities/{opportunity_id}/plan", status_code=201)
def create_automation_plan(opportunity_id: int):
    """Create a guarded plan; only local metadata assessment runs automatically."""
    ensure_tables()
    with connect() as db:
        opportunity = db.execute(
            "SELECT * FROM opportunities WHERE id = ?", (opportunity_id,)
        ).fetchone()
        if not opportunity:
            raise HTTPException(404, "Opportunity not found")

        snapshot = {
            "automation_policy": opportunity["automation_policy"],
            "captcha_required": opportunity["captcha_required"],
            "automation_eligibility": opportunity["automation_eligibility"],
            "opportunity_category": opportunity["opportunity_category"],
            "policy_source": opportunity["policy_source"],
            "policy_evidence_url": opportunity["policy_evidence_url"],
        }
        cur = db.execute(
            """INSERT INTO automation_runs
               (opportunity_id, mode, status, policy_snapshot, created_at)
               VALUES (?, 'guarded_autonomy', 'planned', ?, ?)""",
            (opportunity_id, json.dumps(snapshot, sort_keys=True), now()),
        )
        run_id = cur.lastrowid
        timestamp = now()

        if opportunity["automation_eligibility"] == "auto":
            db.execute(
                """INSERT INTO automation_actions
                   (run_id, opportunity_id, action_type, description, status, result, created_at, updated_at)
                   VALUES (?, ?, 'refresh_local_assessment', ?, 'completed', ?, ?, ?)""",
                (run_id, opportunity_id, ACTION_DESCRIPTIONS["refresh_local_assessment"],
                 json.dumps({"decision": "metadata_gate_passed", "external_site_touched": False}),
                 timestamp, timestamp),
            )
            next_action = "prepare_manual_participation"
        elif opportunity["automation_eligibility"] == "excluded":
            db.execute(
                """INSERT INTO automation_actions
                   (run_id, opportunity_id, action_type, description, status, result, created_at, updated_at)
                   VALUES (?, ?, 'prepare_human_review', ?, 'blocked', ?, ?, ?)""",
                (run_id, opportunity_id, ACTION_DESCRIPTIONS["prepare_human_review"],
                 json.dumps({"decision": "excluded_by_policy", "external_site_touched": False}),
                 timestamp, timestamp),
            )
            next_action = None
        else:
            next_action = "prepare_human_review"

        if next_action:
            db.execute(
                """INSERT INTO automation_actions
                   (run_id, opportunity_id, action_type, description, status, result, created_at, updated_at)
                   VALUES (?, ?, ?, ?, 'pending_approval', ?, ?, ?)""",
                (run_id, opportunity_id, next_action, ACTION_DESCRIPTIONS[next_action],
                 json.dumps({"requires_human_presence": True, "external_site_touched": False}),
                 timestamp, timestamp),
            )

        run_status = 'awaiting_approval' if next_action else 'blocked'
        db.execute("UPDATE automation_runs SET status = ? WHERE id = ?",
                   (run_status, run_id))
        actions = db.execute(
            "SELECT * FROM automation_actions WHERE run_id = ? ORDER BY id", (run_id,)
        ).fetchall()
        return {
            "run_id": run_id,
            "opportunity_id": opportunity_id,
            "mode": "guarded_autonomy",
            "status": "awaiting_approval" if next_action else "blocked",
            "policy_snapshot": snapshot,
            "actions": [action_dict(row) for row in actions],
            "safety_note": "Approval only authorizes a manual handoff; it does not operate the third-party website.",
        }


@router.get("/runs")
def list_automation_runs():
    ensure_tables()
    with connect() as db:
        return [dict(row) for row in db.execute(
            """SELECT automation_runs.*, opportunities.title AS opportunity_title
               FROM automation_runs JOIN opportunities ON opportunities.id = automation_runs.opportunity_id
               ORDER BY automation_runs.created_at DESC"""
        ).fetchall()]


@router.get("/actions")
def list_automation_actions(status: str | None = None):
    ensure_tables()
    with connect() as db:
        if status:
            rows = db.execute(
                "SELECT * FROM automation_actions WHERE status = ? ORDER BY created_at DESC",
                (status,),
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT * FROM automation_actions ORDER BY created_at DESC"
            ).fetchall()
        return [action_dict(row) for row in rows]


@router.post("/actions/{action_id}/approve")
def approve_automation_action(action_id: int):
    """Approve a human handoff only; never trigger third-party interaction."""
    ensure_tables()
    with connect() as db:
        row = db.execute(
            "SELECT * FROM automation_actions WHERE id = ?", (action_id,)
        ).fetchone()
        if not row:
            raise HTTPException(404, "Automation action not found")
        if row["status"] != "pending_approval":
            raise HTTPException(409, "Only pending actions can be approved")
        db.execute(
            "UPDATE automation_actions SET status = 'ready_for_user', updated_at = ? WHERE id = ?",
            (now(), action_id),
        )
        db.execute("UPDATE automation_runs SET status = 'ready_for_user' WHERE id = ?", (row["run_id"],))
        updated = db.execute(
            "SELECT * FROM automation_actions WHERE id = ?", (action_id,)
        ).fetchone()
        return action_dict(updated)


@router.post("/actions/{action_id}/reject")
def reject_automation_action(action_id: int):
    ensure_tables()
    with connect() as db:
        row = db.execute(
            "SELECT * FROM automation_actions WHERE id = ?", (action_id,)
        ).fetchone()
        if not row:
            raise HTTPException(404, "Automation action not found")
        if row["status"] != "pending_approval":
            raise HTTPException(409, "Only pending actions can be rejected")
        db.execute(
            "UPDATE automation_actions SET status = 'rejected', updated_at = ? WHERE id = ?",
            (now(), action_id),
        )
        db.execute("UPDATE automation_runs SET status = 'rejected' WHERE id = ?", (row["run_id"],))
        return action_dict(db.execute(
            "SELECT * FROM automation_actions WHERE id = ?", (action_id,)
        ).fetchone())
