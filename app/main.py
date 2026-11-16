from __future__ import annotations

import os
import sqlite3
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse, urlunparse

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, HttpUrl

from app.policy import derive_automation_eligibility
from app.game_engine import authorize_game_strategy, solve_target_number
from app.game_benchmark import run_target_number_benchmark
from app.deduction_games import filter_word_candidates, solve_mastermind

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.getenv("AUTOEARN_DB", ROOT / "autoearn.db"))
STATIC_DIR = ROOT / "static"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db


def init_db() -> None:
    with connect() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS opportunities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            platform TEXT NOT NULL,
            url TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'game',
            reward_description TEXT NOT NULL DEFAULT '',
            eligibility TEXT NOT NULL DEFAULT '',
            terms_url TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'discovered',
            score INTEGER NOT NULL DEFAULT 0,
            notes TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_opportunities_url ON opportunities(url);
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            opportunity_id INTEGER NOT NULL REFERENCES opportunities(id) ON DELETE CASCADE,
            description TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending_approval',
            approved_at TEXT,
            completed_at TEXT,
            created_at TEXT NOT NULL,
            action_type TEXT NOT NULL DEFAULT 'other',
            requires_approval INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS game_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            opportunity_id INTEGER NOT NULL REFERENCES opportunities(id) ON DELETE CASCADE,
            game_type TEXT NOT NULL,
            solved INTEGER NOT NULL,
            strategy TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS rewards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            opportunity_id INTEGER REFERENCES opportunities(id) ON DELETE SET NULL,
            amount REAL NOT NULL CHECK(amount >= 0),
            currency TEXT NOT NULL DEFAULT 'USD',
            status TEXT NOT NULL DEFAULT 'pending',
            reference TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL
        );
        """)
        # Additive migration keeps existing opportunity records intact.
        existing_columns = {row[1] for row in db.execute("PRAGMA table_info(opportunities)")}
        additions = {
            "automation_policy": "TEXT NOT NULL DEFAULT 'unknown'",
            "captcha_required": "INTEGER",
            "opportunity_category": "TEXT NOT NULL DEFAULT 'ordinary'",
            "automation_eligibility": "TEXT NOT NULL DEFAULT 'manual_only'",
            "policy_source": "TEXT NOT NULL DEFAULT 'unknown'",
            "policy_evidence_url": "TEXT NOT NULL DEFAULT ''",
            "policy_evidence": "TEXT NOT NULL DEFAULT ''",
        }
        for column, declaration in additions.items():
            if column not in existing_columns:
                db.execute(f"ALTER TABLE opportunities ADD COLUMN {column} {declaration}")
        task_columns = {row[1] for row in db.execute("PRAGMA table_info(tasks)")}
        task_additions = {
            "action_type": "TEXT NOT NULL DEFAULT 'other'",
            "requires_approval": "INTEGER NOT NULL DEFAULT 1",
        }
        for column, declaration in task_additions.items():
            if column not in task_columns:
                db.execute(f"ALTER TABLE tasks ADD COLUMN {column} {declaration}")


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="AutoEarn AI",
    description="Human-in-the-loop opportunity discovery and reward tracking.",
    version="0.1.0",
    lifespan=lifespan,
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class OpportunityIn(BaseModel):
    title: str = Field(min_length=2, max_length=160)
    platform: str = Field(min_length=2, max_length=100)
    url: HttpUrl
    category: str = Field(default="game", max_length=40)
    reward_description: str = Field(default="", max_length=500)
    eligibility: str = Field(default="", max_length=1000)
    terms_url: str = Field(default="", max_length=500)
    notes: str = Field(default="", max_length=1000)
    automation_policy: Literal["allowed", "prohibited", "unknown"] = "unknown"
    captcha_required: bool | None = None
    opportunity_category: Literal["ordinary", "giveaway_free", "skill_contest", "paid_lottery", "betting"] = "ordinary"
    policy_source: Literal["terms", "robots_txt", "provider", "manual_review", "unknown"] = "unknown"
    policy_evidence_url: str = Field(default="", max_length=500)
    policy_evidence: str = Field(default="", max_length=500)


class TaskIn(BaseModel):
    opportunity_id: int
    description: str = Field(min_length=3, max_length=500)
    action_type: Literal["site_participation", "claim_reward", "account_action", "other"] = "other"


class GameSolveIn(BaseModel):
    opportunity_id: int
    game_type: Literal["target_number"] = "target_number"
    numbers: list[int] = Field(min_length=2, max_length=7)
    target: int = Field(ge=-10000, le=10000)


class WordDeductionIn(BaseModel):
    opportunity_id: int
    candidates: list[str] = Field(min_length=1, max_length=5000)
    guesses: list[dict[str, str]] = Field(default_factory=list, max_length=20)


class MastermindIn(BaseModel):
    opportunity_id: int
    colors: list[str] = Field(min_length=2, max_length=8)
    length: int = Field(ge=2, le=6)
    history: list[dict] = Field(default_factory=list, max_length=20)


class RewardIn(BaseModel):
    opportunity_id: int | None = None
    amount: float = Field(ge=0)
    currency: str = Field(default="USD", min_length=3, max_length=8)
    status: Literal["pending", "confirmed", "paid", "rejected"] = "pending"
    reference: str = Field(default="", max_length=200)


def row_dict(row: sqlite3.Row) -> dict:
    return dict(row)


def normalize_url(value: str) -> str:
    parsed = urlparse(value.strip())
    path = parsed.path.rstrip("/") or "/"
    return urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), path, "", parsed.query, ""))


def safe_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


@app.get("/", include_in_schema=False)
def home():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "AutoEarn AI", "version": app.version}


@app.get("/api/opportunities")
def list_opportunities(status: str | None = None, q: str | None = Query(default=None, max_length=100)):
    sql, params = "SELECT * FROM opportunities", []
    clauses = []
    if status:
        clauses.append("status = ?")
        params.append(status)
    if q:
        clauses.append("(title LIKE ? OR platform LIKE ? OR category LIKE ?)")
        params.extend([f"%{q}%"] * 3)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY created_at DESC"
    with connect() as db:
        return [row_dict(r) for r in db.execute(sql, params).fetchall()]


@app.post("/api/opportunities", status_code=201)
def create_opportunity(data: OpportunityIn):
    payload = data.model_dump()
    payload["url"] = normalize_url(str(payload["url"]))
    if not safe_url(payload["url"]):
        raise HTTPException(422, "Only public http/https opportunity URLs are accepted.")
    if payload["terms_url"] and not safe_url(payload["terms_url"]):
        raise HTTPException(422, "Terms URL must be an http/https URL.")
    if payload["policy_evidence_url"] and not safe_url(payload["policy_evidence_url"]):
        raise HTTPException(422, "Policy evidence URL must be an http/https URL.")
    payload["automation_eligibility"] = derive_automation_eligibility(
        payload["automation_policy"], payload["captcha_required"], payload["opportunity_category"],
        payload["policy_source"], payload["policy_evidence_url"], payload["policy_evidence"],
    )
    score = 20
    score += 25 if payload["terms_url"] else 0
    score += 20 if payload["eligibility"] else 0
    score += 15 if payload["reward_description"] else 0
    score += 20 if payload["notes"] else 0
    with connect() as db:
        existing = db.execute("SELECT id FROM opportunities WHERE url = ?", (payload["url"],)).fetchone()
        if existing:
            raise HTTPException(409, "This opportunity URL is already registered.")
        cur = db.execute("""
            INSERT INTO opportunities
            (title, platform, url, category, reward_description, eligibility, terms_url, notes, score, created_at,
             automation_policy, captcha_required, opportunity_category, automation_eligibility,
             policy_source, policy_evidence_url, policy_evidence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (payload["title"], payload["platform"], payload["url"], payload["category"],
              payload["reward_description"], payload["eligibility"], payload["terms_url"],
              payload["notes"], score, now(), payload["automation_policy"],
              None if payload["captcha_required"] is None else int(payload["captcha_required"]),
              payload["opportunity_category"], payload["automation_eligibility"],
              payload["policy_source"], payload["policy_evidence_url"], payload["policy_evidence"]))
        row = db.execute("SELECT * FROM opportunities WHERE id = ?", (cur.lastrowid,)).fetchone()
        return row_dict(row)


@app.get("/api/opportunities/automation-eligible")
def list_automation_eligible_opportunities():
    """Return only opportunities with explicit policy clearance and supporting evidence."""
    with connect() as db:
        return [row_dict(r) for r in db.execute(
            "SELECT * FROM opportunities WHERE automation_eligibility = 'auto' ORDER BY created_at DESC"
        ).fetchall()]


@app.patch("/api/opportunities/{opportunity_id}/status")
def update_opportunity_status(opportunity_id: int, status: Literal["discovered", "reviewing", "eligible", "ineligible", "archived"]):
    with connect() as db:
        cur = db.execute("UPDATE opportunities SET status = ? WHERE id = ?", (status, opportunity_id))
        if not cur.rowcount:
            raise HTTPException(404, "Opportunity not found")
        return row_dict(db.execute("SELECT * FROM opportunities WHERE id = ?", (opportunity_id,)).fetchone())


@app.post("/api/tasks", status_code=201)
def create_task(data: TaskIn):
    # User-submitted tasks are always external or unspecified and require approval.
    requires_approval = True
    status = "pending_approval"
    with connect() as db:
        if not db.execute("SELECT id FROM opportunities WHERE id = ?", (data.opportunity_id,)).fetchone():
            raise HTTPException(404, "Opportunity not found")
        cur = db.execute(
            """INSERT INTO tasks
            (opportunity_id, description, status, created_at, action_type, requires_approval)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (data.opportunity_id, data.description, status, now(), data.action_type, int(requires_approval)),
        )
        return row_dict(db.execute("SELECT * FROM tasks WHERE id = ?", (cur.lastrowid,)).fetchone())


@app.post("/api/automation/prepare")
def prepare_automation_queue():
    """Automatically prepare internal review tasks for policy-cleared opportunities only."""
    created = []
    with connect() as db:
        opportunities = db.execute(
            """SELECT id, title FROM opportunities
            WHERE automation_eligibility = 'auto'
            ORDER BY score DESC, created_at DESC"""
        ).fetchall()
        for opportunity in opportunities:
            exists = db.execute(
                """SELECT id FROM tasks
                WHERE opportunity_id = ? AND action_type = 'internal_review'
                AND status IN ('auto_queued', 'approved', 'completed')""",
                (opportunity["id"],),
            ).fetchone()
            if exists:
                continue
            cur = db.execute(
                """INSERT INTO tasks
                (opportunity_id, description, status, created_at, action_type, requires_approval)
                VALUES (?, ?, 'auto_queued', ?, 'internal_review', 0)""",
                (opportunity["id"], f"Prepare internal review for {opportunity['title']}", now()),
            )
            created.append(cur.lastrowid)
        rows = [row_dict(db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone())
                for task_id in created]
    return {"created_count": len(created), "tasks": rows,
            "note": "Only internal preparation is queued; no third-party site is opened or actioned."}


@app.get("/api/automation/status")
def automation_status():
    with connect() as db:
        counts = {
            row["status"]: row["count"]
            for row in db.execute("SELECT status, COUNT(*) AS count FROM tasks GROUP BY status")
        }
        eligible = db.execute(
            "SELECT COUNT(*) FROM opportunities WHERE automation_eligibility = 'auto'"
        ).fetchone()[0]
        manual = db.execute(
            "SELECT COUNT(*) FROM opportunities WHERE automation_eligibility = 'manual_only'"
        ).fetchone()[0]
        excluded = db.execute(
            "SELECT COUNT(*) FROM opportunities WHERE automation_eligibility = 'excluded'"
        ).fetchone()[0]
    return {
        "mode": "maximum_compliant",
        "policy_gate": "fail_closed",
        "auto_eligible_opportunities": eligible,
        "manual_only_opportunities": manual,
        "excluded_opportunities": excluded,
        "task_counts": counts,
        "external_actions_require_approval": True,
        "captcha_bypass_enabled": False,
        "automated_ad_views_enabled": False,
        "automated_gameplay_enabled": False,
    }


@app.post("/api/games/solve")
def solve_skill_game(data: GameSolveIn):
    """Analyze a skill-game round locally; never plays or submits to a third-party site."""
    with connect() as db:
        row = db.execute("SELECT * FROM opportunities WHERE id = ?", (data.opportunity_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Opportunity not found")
        try:
            authorize_game_strategy(row_dict(row))
            result = solve_target_number(data.numbers, data.target)
        except PermissionError as exc:
            raise HTTPException(403, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        db.execute("INSERT INTO game_runs (opportunity_id, game_type, solved, strategy, created_at) VALUES (?, ?, ?, ?, ?)",
                   (data.opportunity_id, data.game_type, int(result["solved"]), result["strategy"], now()))
    return {**result, "mode": "analysis_only", "site_played": False,
            "note": "Only the supplied puzzle state was analyzed; no external game action was taken."}


@app.get("/api/games/benchmark")
def skill_game_benchmark(rounds: int | None = Query(default=None, ge=1, le=10)):
    """Run a deterministic local benchmark; no third-party site is contacted."""
    try:
        return run_target_number_benchmark(rounds)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.post("/api/games/word/filter")
def filter_word_game(data: WordDeductionIn):
    """Filter user-supplied word candidates locally; no site interaction occurs."""
    with connect() as db:
        row = db.execute("SELECT * FROM opportunities WHERE id = ?", (data.opportunity_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Opportunity not found")
        try:
            authorize_game_strategy(row_dict(row))
            return filter_word_candidates(data.candidates, data.guesses)
        except PermissionError as exc:
            raise HTTPException(403, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc


@app.post("/api/games/logic/mastermind")
def solve_logic_game(data: MastermindIn):
    """Deduce possible Mastermind codes from supplied feedback; no external play."""
    with connect() as db:
        row = db.execute("SELECT * FROM opportunities WHERE id = ?", (data.opportunity_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Opportunity not found")
        try:
            authorize_game_strategy(row_dict(row))
            return solve_mastermind(data.colors, data.length, data.history)
        except PermissionError as exc:
            raise HTTPException(403, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc


@app.get("/api/games/stats")
def skill_game_stats():
    with connect() as db:
        row = db.execute("SELECT COUNT(*) AS attempts, COALESCE(SUM(solved), 0) AS solved FROM game_runs").fetchone()
    attempts, solved = row["attempts"], row["solved"]
    return {"attempts": attempts, "solved": solved,
            "solve_rate": round(solved / attempts, 4) if attempts else None,
            "metric": "local_puzzle_solve_rate_not_platform_win_rate"}

@app.get("/api/tasks")
def list_tasks():
    with connect() as db:
        return [row_dict(r) for r in db.execute("""
            SELECT tasks.*, opportunities.title AS opportunity_title, opportunities.platform
            FROM tasks JOIN opportunities ON opportunities.id = tasks.opportunity_id
            ORDER BY tasks.created_at DESC
        """).fetchall()]


@app.post("/api/tasks/{task_id}/approve")
def approve_task(task_id: int):
    with connect() as db:
        row = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Task not found")
        if row["status"] != "pending_approval":
            raise HTTPException(409, "Only tasks awaiting approval can be approved")
        db.execute("UPDATE tasks SET status = 'approved', approved_at = ? WHERE id = ?", (now(), task_id))
        return row_dict(db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone())


@app.post("/api/tasks/{task_id}/complete")
def complete_task(task_id: int):
    with connect() as db:
        row = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Task not found")
        if row["status"] not in {"approved", "auto_queued"}:
            raise HTTPException(409, "A task must be approved or internally auto-queued before it can be marked complete")
        db.execute("UPDATE tasks SET status = 'completed', completed_at = ? WHERE id = ?", (now(), task_id))
        return row_dict(db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone())


@app.get("/api/rewards")
def list_rewards():
    with connect() as db:
        return [row_dict(r) for r in db.execute("""
            SELECT rewards.*, opportunities.title AS opportunity_title
            FROM rewards LEFT JOIN opportunities ON opportunities.id = rewards.opportunity_id
            ORDER BY rewards.created_at DESC
        """).fetchall()]


@app.post("/api/rewards", status_code=201)
def create_reward(data: RewardIn):
    with connect() as db:
        if data.opportunity_id is not None and not db.execute(
            "SELECT id FROM opportunities WHERE id = ?", (data.opportunity_id,)
        ).fetchone():
            raise HTTPException(404, "Opportunity not found")
        cur = db.execute("""
            INSERT INTO rewards (opportunity_id, amount, currency, status, reference, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (data.opportunity_id, data.amount, data.currency.upper(), data.status, data.reference, now()))
        return row_dict(db.execute("SELECT * FROM rewards WHERE id = ?", (cur.lastrowid,)).fetchone())


@app.get("/api/dashboard")
def dashboard():
    with connect() as db:
        opportunities = db.execute("SELECT COUNT(*) FROM opportunities").fetchone()[0]
        tasks = db.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        awaiting = db.execute("SELECT COUNT(*) FROM tasks WHERE status = 'pending_approval'").fetchone()[0]
        paid = db.execute("SELECT COALESCE(SUM(amount), 0) FROM rewards WHERE status = 'paid'").fetchone()[0]
        pending = db.execute("SELECT COALESCE(SUM(amount), 0) FROM rewards WHERE status = 'pending'").fetchone()[0]
        return {"opportunities": opportunities, "tasks": tasks, "awaiting_approval": awaiting,
                "paid_total": round(paid, 2), "pending_total": round(pending, 2)}
