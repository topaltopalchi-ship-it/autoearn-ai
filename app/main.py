from __future__ import annotations

import ipaddress
import json
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

from autoearn.opportunities import BraveSearchProvider, discover_opportunities, normalize_url
from autoearn.mwmbl import MwmblSearchProvider
from autoearn.extraction import extract_opportunity_details
from autoearn.catalog import expand_discovery_query
from pydantic import BaseModel, Field, HttpUrl

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
        CREATE TABLE IF NOT EXISTS discovered_candidates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            canonical_url TEXT NOT NULL UNIQUE,
            snippet TEXT NOT NULL DEFAULT '',
            provider TEXT NOT NULL,
            domain TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'all',
            discovered_at TEXT NOT NULL,
            confidence INTEGER NOT NULL CHECK(confidence BETWEEN 0 AND 100),
            signals_json TEXT NOT NULL DEFAULT '[]',
            review_required INTEGER NOT NULL DEFAULT 1,
            review_status TEXT NOT NULL DEFAULT 'pending' CHECK(review_status IN ('pending', 'accepted', 'rejected')),
            reviewed_at TEXT,
            review_note TEXT NOT NULL DEFAULT '',
            extraction_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            opportunity_id INTEGER NOT NULL REFERENCES opportunities(id) ON DELETE CASCADE,
            description TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending_approval',
            approved_at TEXT,
            completed_at TEXT,
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
        # Additive migration for databases created by earlier discovery builds.
        candidate_columns = {row["name"] for row in db.execute("PRAGMA table_info(discovered_candidates)")}
        if "review_status" not in candidate_columns:
            db.execute("ALTER TABLE discovered_candidates ADD COLUMN review_status TEXT NOT NULL DEFAULT 'pending'")
        if "reviewed_at" not in candidate_columns:
            db.execute("ALTER TABLE discovered_candidates ADD COLUMN reviewed_at TEXT")
        if "review_note" not in candidate_columns:
            db.execute("ALTER TABLE discovered_candidates ADD COLUMN review_note TEXT NOT NULL DEFAULT ''")
        if "extraction_json" not in candidate_columns:
            db.execute("ALTER TABLE discovered_candidates ADD COLUMN extraction_json TEXT NOT NULL DEFAULT '{}'")
        if "category" not in candidate_columns:
            db.execute("ALTER TABLE discovered_candidates ADD COLUMN category TEXT NOT NULL DEFAULT 'all'")


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


class DiscoverIn(BaseModel):
    query: str = Field(min_length=1, max_length=220)
    category: Literal["all", "games", "surveys", "user_testing", "microtasks", "freelance", "cashback", "affiliate", "creator", "tutoring", "digital_products", "research", "bug_bounty"] = "all"
    limit: int = Field(default=10, ge=1, le=20)


class CandidateReviewIn(BaseModel):
    status: Literal["accepted", "rejected"]
    note: str = Field(default="", max_length=1000)


class CandidateExtractIn(BaseModel):
    page_text: str = Field(min_length=1, max_length=20000)


class OpportunityIn(BaseModel):
    title: str = Field(min_length=2, max_length=160)
    platform: str = Field(min_length=2, max_length=100)
    url: HttpUrl
    category: str = Field(default="game", max_length=40)
    reward_description: str = Field(default="", max_length=500)
    eligibility: str = Field(default="", max_length=1000)
    terms_url: str = Field(default="", max_length=500)
    notes: str = Field(default="", max_length=1000)


class TaskIn(BaseModel):
    opportunity_id: int
    description: str = Field(min_length=3, max_length=500)


class RewardIn(BaseModel):
    opportunity_id: int | None = None
    amount: float = Field(ge=0)
    currency: str = Field(default="USD", min_length=3, max_length=8)
    status: Literal["pending", "confirmed", "paid", "rejected"] = "pending"
    reference: str = Field(default="", max_length=200)


def row_dict(row: sqlite3.Row) -> dict:
    return dict(row)


def safe_url(value: str) -> bool:
    """Accept canonical public HTTP(S) URLs; reject credentials and local IP hosts."""
    try:
        canonical = normalize_url(value)
    except (TypeError, ValueError):
        return False
    host = (urlparse(canonical).hostname or "").lower().rstrip(".")
    if not host or host == "localhost" or host.endswith(".localhost"):
        return False
    try:
        return ipaddress.ip_address(host).is_global
    except ValueError:
        # Opportunity metadata is never fetched server-side; domain names are
        # retained as links for manual review, not used as network destinations.
        return True


@app.get("/", include_in_schema=False)
def home():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "AutoEarn AI", "version": app.version}


@app.post("/api/discover")
def discover(data: DiscoverIn):
    brave_key = os.getenv("BRAVE_SEARCH_API_KEY", "").strip()
    mwmbl_key = os.getenv("MWMBL_API_KEY", "").strip()
    try:
        # Prefer Brave when explicitly configured; otherwise use Mwmbl's
        # anonymous free tier (1,000 requests/month, 1 request/second).
        provider = BraveSearchProvider(brave_key) if brave_key else MwmblSearchProvider(api_key=mwmbl_key or None)
        expanded_query = expand_discovery_query(data.query, data.category)
        results = discover_opportunities(
            expanded_query,
            provider,
            limit=data.limit,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(502, "The search provider is temporarily unavailable.") from exc

    saved = []
    with connect() as db:
        for item in results:
            cursor = db.execute(
                """
                INSERT OR IGNORE INTO discovered_candidates
                (title, canonical_url, snippet, provider, domain, category, discovered_at,
                 confidence, signals_json, review_required, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
                """,
                (
                    item.title, item.url, item.snippet, item.provider, item.domain, data.category,
                    item.discovered_at, item.confidence, json.dumps(list(item.signals)), now(),
                ),
            )
            row = db.execute(
                "SELECT * FROM discovered_candidates WHERE canonical_url = ?", (item.url,)
            ).fetchone()
            saved.append({
                "id": row["id"],
                "title": row["title"],
                "url": row["canonical_url"],
                "snippet": row["snippet"],
                "provider": row["provider"],
                "domain": row["domain"],
                "category": row["category"],
                "discovered_at": row["discovered_at"],
                "confidence": row["confidence"],
                "signals": json.loads(row["signals_json"]),
                "review_required": bool(row["review_required"]),
                "verified": False,
                "is_new": cursor.rowcount == 1,
            })
    return saved


@app.get("/api/discoveries")
def list_discoveries():
    with connect() as db:
        rows = db.execute(
            "SELECT * FROM discovered_candidates ORDER BY created_at DESC, id DESC"
        ).fetchall()
    return [
        {
            "id": row["id"],
            "title": row["title"],
            "url": row["canonical_url"],
            "snippet": row["snippet"],
            "provider": row["provider"],
            "domain": row["domain"],
            "category": row["category"],
            "discovered_at": row["discovered_at"],
            "confidence": row["confidence"],
            "signals": json.loads(row["signals_json"]),
            "review_required": bool(row["review_required"]),
            "review_status": row["review_status"],
            "reviewed_at": row["reviewed_at"],
            "review_note": row["review_note"],
            "extraction": json.loads(row["extraction_json"]),
            "verified": False,
        }
        for row in rows
    ]


@app.post("/api/discoveries/{candidate_id}/extract")
def extract_discovery(candidate_id: int, data: CandidateExtractIn):
    """Analyze user-supplied page text; this endpoint never fetches the URL."""
    try:
        extracted = extract_opportunity_details(data.page_text)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    with connect() as db:
        if not db.execute("SELECT id FROM discovered_candidates WHERE id = ?", (candidate_id,)).fetchone():
            raise HTTPException(404, "Discovered candidate not found")
        db.execute(
            "UPDATE discovered_candidates SET extraction_json = ? WHERE id = ?",
            (json.dumps(extracted), candidate_id),
        )
    return {"candidate_id": candidate_id, "extraction": extracted}


@app.patch("/api/discoveries/{candidate_id}/review")
def review_discovery(candidate_id: int, data: CandidateReviewIn):
    """Record a human triage decision without verifying or activating a candidate."""
    with connect() as db:
        if not db.execute("SELECT id FROM discovered_candidates WHERE id = ?", (candidate_id,)).fetchone():
            raise HTTPException(404, "Discovered candidate not found")
        db.execute(
            "UPDATE discovered_candidates SET review_status = ?, reviewed_at = ?, review_note = ? WHERE id = ?",
            (data.status, now(), data.note.strip(), candidate_id),
        )
        row = db.execute("SELECT * FROM discovered_candidates WHERE id = ?", (candidate_id,)).fetchone()
    result = row_dict(row)
    result["signals"] = json.loads(result.pop("signals_json"))
    result["review_required"] = bool(result["review_required"])
    result["verified"] = False
    return result


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
    # Completeness score for the API record (0-100), not a legitimacy guarantee.
    score = 20  # Required title and platform fields are present.
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
            (title, platform, url, category, reward_description, eligibility, terms_url, notes, score, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (payload["title"], payload["platform"], payload["url"], payload["category"],
              payload["reward_description"], payload["eligibility"], payload["terms_url"],
              payload["notes"], score, now()))
        row = db.execute("SELECT * FROM opportunities WHERE id = ?", (cur.lastrowid,)).fetchone()
        return row_dict(row)


@app.patch("/api/opportunities/{opportunity_id}/status")
def update_opportunity_status(opportunity_id: int, status: Literal["discovered", "reviewing", "eligible", "ineligible", "archived"]):
    with connect() as db:
        cur = db.execute("UPDATE opportunities SET status = ? WHERE id = ?", (status, opportunity_id))
        if not cur.rowcount:
            raise HTTPException(404, "Opportunity not found")
        return row_dict(db.execute("SELECT * FROM opportunities WHERE id = ?", (opportunity_id,)).fetchone())


@app.post("/api/tasks", status_code=201)
def create_task(data: TaskIn):
    with connect() as db:
        if not db.execute("SELECT id FROM opportunities WHERE id = ?", (data.opportunity_id,)).fetchone():
            raise HTTPException(404, "Opportunity not found")
        cur = db.execute("INSERT INTO tasks (opportunity_id, description, created_at) VALUES (?, ?, ?)",
                         (data.opportunity_id, data.description, now()))
        return row_dict(db.execute("SELECT * FROM tasks WHERE id = ?", (cur.lastrowid,)).fetchone())


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
        if row["status"] != "approved":
            raise HTTPException(409, "A task must be approved before it can be marked complete")
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
