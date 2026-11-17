from __future__ import annotations

import json
import os
import hmac
import sqlite3
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Query, Depends, Header
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, HttpUrl

from autoearn.opportunities import normalize_url
from autoearn.supervision_store import SQLiteSupervisionStore
from autoearn.supervision import SupervisionError
from autoearn.rss import PublicRssAdapter
from autoearn.evaluator import OpportunityCandidate, evaluate_candidate

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.getenv("AUTOEARN_DB", ROOT / "autoearn.db"))
OWNER_TOKEN = os.getenv("AUTOEARN_OWNER_TOKEN", "")
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
            created_at TEXT NOT NULL,
            eligible_countries TEXT NOT NULL DEFAULT '[]',
            excluded_countries TEXT NOT NULL DEFAULT '[]',
            minimum_withdrawal_amount REAL,
            withdrawal_currency TEXT NOT NULL DEFAULT 'USD',
            payout_methods TEXT NOT NULL DEFAULT '[]',
            verification_status TEXT NOT NULL DEFAULT 'pending',
            verified_at TEXT,
            verification_notes TEXT NOT NULL DEFAULT ''
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_opportunities_url ON opportunities(url);
        CREATE TABLE IF NOT EXISTS sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            url TEXT NOT NULL UNIQUE,
            category TEXT NOT NULL DEFAULT 'game_rewards',
            terms_url TEXT NOT NULL DEFAULT '',
            country_notes TEXT NOT NULL DEFAULT '',
            payment_notes TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'pending',
            discovered_at TEXT NOT NULL,
            review_notes TEXT NOT NULL DEFAULT ''
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
        CREATE TABLE IF NOT EXISTS earnings_ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            opportunity_id INTEGER REFERENCES opportunities(id) ON DELETE SET NULL,
            amount REAL NOT NULL CHECK(amount >= 0),
            currency TEXT NOT NULL DEFAULT 'EUR',
            state TEXT NOT NULL DEFAULT 'estimated'
                CHECK(state IN ('estimated', 'earned', 'pending', 'withdrawable', 'paid')),
            reference TEXT NOT NULL DEFAULT '',
            evidence TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_earnings_ledger_created
            ON earnings_ledger(created_at DESC, id DESC);
        CREATE TABLE IF NOT EXISTS earnings_ledger_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ledger_id INTEGER NOT NULL REFERENCES earnings_ledger(id) ON DELETE CASCADE,
            actor TEXT NOT NULL,
            from_state TEXT,
            to_state TEXT NOT NULL,
            note TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_earnings_events_ledger
            ON earnings_ledger_events(ledger_id, created_at, id);
        CREATE TABLE IF NOT EXISTS evaluation_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            opportunity_id INTEGER NOT NULL REFERENCES opportunities(id) ON DELETE CASCADE,
            source_id INTEGER NOT NULL REFERENCES sources(id) ON DELETE RESTRICT,
            country TEXT NOT NULL,
            execution_mode TEXT NOT NULL,
            request_json TEXT NOT NULL,
            result_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_evaluation_history_opportunity
            ON evaluation_history(opportunity_id, created_at DESC);
        """)
        # Additive migration for databases created by earlier MVP versions.
        columns = {row["name"] for row in db.execute("PRAGMA table_info(opportunities)")}
        migrations = {
            "eligible_countries": "TEXT NOT NULL DEFAULT '[]'",
            "excluded_countries": "TEXT NOT NULL DEFAULT '[]'",
            "minimum_withdrawal_amount": "REAL",
            "withdrawal_currency": "TEXT NOT NULL DEFAULT 'USD'",
            "payout_methods": "TEXT NOT NULL DEFAULT '[]'",
            "verification_status": "TEXT NOT NULL DEFAULT 'pending'",
            "verified_at": "TEXT",
            "verification_notes": "TEXT NOT NULL DEFAULT ''",
        }
        for name, definition in migrations.items():
            if name not in columns:
                db.execute(f"ALTER TABLE opportunities ADD COLUMN {name} {definition}")


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
    eligible_countries: list[str] = Field(default_factory=list, max_length=100)
    excluded_countries: list[str] = Field(default_factory=list, max_length=100)
    minimum_withdrawal_amount: float | None = Field(default=None, ge=0)
    withdrawal_currency: str = Field(default="USD", min_length=3, max_length=8)    payout_methods: list[str] = Field(default_factory=list, max_length=30)


class SourceIn(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    url: HttpUrl
    category: str = Field(default="game_rewards", min_length=2, max_length=40)
    terms_url: str = Field(default="", max_length=500)
    country_notes: str = Field(default="", max_length=1000)
    payment_notes: str = Field(default="", max_length=1000)


class SourceReviewIn(BaseModel):
    status: Literal["pending", "approved", "rejected"]
    notes: str = Field(default="", max_length=1000)


class VerificationIn(BaseModel):
    status: Literal["pending", "verified", "rejected"]
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

class EarningsLedgerIn(BaseModel):
    opportunity_id: int | None = None
    amount: float = Field(ge=0)
    currency: str = Field(default="EUR", min_length=3, max_length=8)
    state: Literal["estimated", "earned", "pending", "withdrawable", "paid"] = "estimated"
    reference: str = Field(default="", max_length=200)
    evidence: str = Field(default="", max_length=1000)


class EarningsStateIn(BaseModel):
    state: Literal["estimated", "earned", "pending", "withdrawable", "paid"]
    note: str = Field(default="", max_length=1000)


class SupervisedActionIn(BaseModel):
    opportunity_id: int = Field(gt=0)
    source_id: int = Field(gt=0)
    action: Literal["read_public_info", "prepare_draft", "submit_application", "accept_terms", "publish_content", "share_personal_data", "spend_money", "withdraw_funds"]
    description: str = Field(min_length=3, max_length=500)


class ActionDecisionIn(BaseModel):
    reason: str = Field(default="", max_length=1000)


class ActionCompletionIn(BaseModel):
    evidence: str = Field(min_length=3, max_length=1000)

class RssDiscoveryIn(BaseModel):
    adapter_id: str = Field(min_length=2, max_length=80)
    display_name: str = Field(min_length=2, max_length=120)
    feed_url: HttpUrl
    category: Literal["games_competitions", "surveys_microtasks", "freelancing_services", "ai_content_products", "other"]
    allowed_domains: list[str] = Field(min_length=1, max_length=20)
    max_items: int = Field(default=30, ge=1, le=100)

class OpportunityEvaluationIn(BaseModel):
    source_id: int = Field(gt=0)
    country: str = Field(min_length=2, max_length=80)
    execution_mode: Literal["manual", "assist", "official_api"] = "manual"
    reward_amount: float | None = Field(default=None, ge=0)
    reward_currency: str = Field(default="EUR", min_length=3, max_length=8)
    estimated_cost: float = Field(default=0, ge=0)
    payout_fee_fixed: float = Field(default=0, ge=0)
    payout_fee_percent: float = Field(default=0, ge=0, le=100)
    conversion_fee_percent: float = Field(default=0, ge=0, le=100)
    estimated_minutes: int | None = Field(default=None, gt=0)
    payment_probability: int | None = Field(default=None, ge=0, le=100)
    risk_score: int | None = Field(default=None, ge=0, le=100)
    evidence: list[str] = Field(default_factory=list, max_length=20)


def require_owner(x_autoearn_owner_token: str | None = Header(default=None)):
    configured = OWNER_TOKEN
    if len(configured) < 32:
        raise HTTPException(503, "Owner actions are disabled: AUTOEARN_OWNER_TOKEN must contain at least 32 characters.")
    if not x_autoearn_owner_token or not hmac.compare_digest(
        x_autoearn_owner_token.encode("utf-8"), configured.encode("utf-8")
    ):
        raise HTTPException(401, "Owner authentication required.")
    return "owner"


def row_dict(row: sqlite3.Row) -> dict:
    result = dict(row)
    for field in ("eligible_countries", "excluded_countries", "payout_methods"):
        if field in result:
            try:
                result[field] = json.loads(result[field] or "[]")
            except (TypeError, json.JSONDecodeError):
                result[field] = []
    return result


def safe_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc) and not parsed.username and not parsed.password


def clean_list(values: list[str], field: str) -> list[str]:
    cleaned = []
    seen = set()
    for value in values:
        item = value.strip()
        if not item:
            continue
        key = item.casefold()
        if key not in seen:
            cleaned.append(item[:80])
            seen.add(key)
    return cleaned


@app.get("/", include_in_schema=False)
def home():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "AutoEarn AI", "version": app.version}


@app.get("/api/opportunities")
def list_opportunities(status: str | None = None, verification_status: Literal["pending", "verified", "rejected"] | None = None, q: str | None = Query(default=None, max_length=100)):
    sql, params = "SELECT * FROM opportunities", []
    clauses = []
    if status:
        clauses.append("status = ?")
        params.append(status)
    if verification_status:
        clauses.append("verification_status = ?")
        params.append(verification_status)
    if q:
        clauses.append("(title LIKE ? OR platform LIKE ? OR category LIKE ?)")
        params.extend([f"%{q}%"] * 3)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY created_at DESC"
    with connect() as db:
        return [row_dict(r) for r in db.execute(sql, params).fetchall()]


@app.post("/api/opportunities", status_code=201)
def create_opportunity(data: OpportunityIn, actor: str = Depends(require_owner)):
    payload = data.model_dump()
    payload["url"] = normalize_url(str(payload["url"]))
    if not safe_url(payload["url"]):
        raise HTTPException(422, "Only public http/https opportunity URLs are accepted.")
    if payload["terms_url"]:
        try:
            payload["terms_url"] = normalize_url(payload["terms_url"])
        except ValueError:
            raise HTTPException(422, "Terms URL must be a safe http/https URL.")
        if not safe_url(payload["terms_url"]):
            raise HTTPException(422, "Terms URL must be a safe http/https URL.")
    for field in ("eligible_countries", "excluded_countries", "payout_methods"):
        payload[field] = json.dumps(clean_list(payload[field], field), ensure_ascii=False)
    payload["withdrawal_currency"] = payload["withdrawal_currency"].strip().upper()
    # API completeness score: normalize the three metadata fields available
    # in this form to a 0-100 scale (40 + 30 + 30). This is distinct from
    # autoearn.opportunities.score_opportunity(), which scores five explicit
    # user-assessed dimensions.
    score = (
        (40 if payload["terms_url"] else 0)
        + (30 if payload["eligibility"] else 0)
        + (30 if payload["reward_description"] else 0)
    )
    with connect() as db:        existing = db.execute("SELECT id FROM opportunities WHERE url = ?", (payload["url"],)).fetchone()
        if existing:
            raise HTTPException(409, "This opportunity URL is already registered.")
        try:
            cur = db.execute("""
                INSERT INTO opportunities
                (title, platform, url, category, reward_description, eligibility, terms_url, notes, score, created_at,
                 eligible_countries, excluded_countries, minimum_withdrawal_amount, withdrawal_currency, payout_methods,
                 verification_status, verified_at, verification_notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', NULL, '')
            """, (payload["title"], payload["platform"], payload["url"], payload["category"],
                  payload["reward_description"], payload["eligibility"], payload["terms_url"],
                  payload["notes"], score, now(), payload["eligible_countries"], payload["excluded_countries"],
                  payload["minimum_withdrawal_amount"], payload["withdrawal_currency"], payload["payout_methods"]))
        except sqlite3.IntegrityError:
            # The pre-insert SELECT is only a friendly fast path. The unique
            # index is the concurrency-safe authority when two requests race.
            existing = db.execute(
                "SELECT id FROM opportunities WHERE url = ?", (payload["url"],)
            ).fetchone()
            if existing:
                raise HTTPException(409, "This opportunity URL is already registered.")
            raise
        row = db.execute("SELECT * FROM opportunities WHERE id = ?", (cur.lastrowid,)).fetchone()
        return row_dict(row)


@app.get("/api/sources")
def list_sources(status: Literal["pending", "approved", "rejected"] | None = None):
    sql = "SELECT * FROM sources"
    params = ()
    if status:
        sql += " WHERE status = ?"
        params = (status,)
    sql += " ORDER BY discovered_at DESC, id DESC"
    with connect() as db:
        return [row_dict(row) for row in db.execute(sql, params).fetchall()]


@app.post("/api/sources", status_code=201)
def create_source(data: SourceIn, actor: str = Depends(require_owner)):
    payload = data.model_dump()
    payload["url"] = normalize_url(str(payload["url"]))
    if not safe_url(payload["url"]):
        raise HTTPException(422, "Only public http/https source URLs are accepted.")
    if payload["terms_url"]:
        try:
            payload["terms_url"] = normalize_url(payload["terms_url"])
        except ValueError:
            raise HTTPException(422, "Terms URL must be a safe http/https URL.")
        if not safe_url(payload["terms_url"]):
            raise HTTPException(422, "Terms URL must be a safe http/https URL.")
    discovered_at = now()
    with connect() as db:
        try:
            cur = db.execute("""
                INSERT INTO sources
                (name, url, category, terms_url, country_notes, payment_notes,
                 status, discovered_at, review_notes)
                VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, '')
            """, (
                payload["name"].strip(), payload["url"], payload["category"].strip().lower(),
                payload["terms_url"], payload["country_notes"].strip(),
                payload["payment_notes"].strip(), discovered_at,
            ))
        except sqlite3.IntegrityError:
            raise HTTPException(409, "This source URL is already registered.")
        return row_dict(db.execute(
            "SELECT * FROM sources WHERE id = ?", (cur.lastrowid,)
        ).fetchone())


@app.patch("/api/sources/{source_id}/review")
def review_source(source_id: int, data: SourceReviewIn, actor: str = Depends(require_owner)):
    with connect() as db:
        row = db.execute("SELECT id FROM sources WHERE id = ?", (source_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Source not found")
        db.execute(
            "UPDATE sources SET status = ?, review_notes = ? WHERE id = ?",
            (data.status, data.notes.strip(), source_id),
        )
        return row_dict(db.execute(
            "SELECT * FROM sources WHERE id = ?", (source_id,)
        ).fetchone())


@app.patch("/api/opportunities/{opportunity_id}/status")
def update_opportunity_status(opportunity_id: int, status: Literal["discovered", "reviewing", "eligible", "ineligible", "archived"], actor: str = Depends(require_owner)):
    with connect() as db:
        cur = db.execute("UPDATE opportunities SET status = ? WHERE id = ?", (status, opportunity_id))
        if not cur.rowcount:
            raise HTTPException(404, "Opportunity not found")
        return row_dict(db.execute("SELECT * FROM opportunities WHERE id = ?", (opportunity_id,)).fetchone())


@app.patch("/api/opportunities/{opportunity_id}/verification")
def update_opportunity_verification(opportunity_id: int, data: VerificationIn, actor: str = Depends(require_owner)):
    """Record a human review decision; only explicit verification sets verified_at."""
    with connect() as db:
        row = db.execute("SELECT id FROM opportunities WHERE id = ?", (opportunity_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Opportunity not found")
        verified_at = now() if data.status == "verified" else None
        db.execute("""
            UPDATE opportunities
            SET verification_status = ?, verified_at = ?, verification_notes = ?
            WHERE id = ?
        """, (data.status, verified_at, data.notes.strip(), opportunity_id))
        return row_dict(db.execute(
            "SELECT * FROM opportunities WHERE id = ?", (opportunity_id,)
        ).fetchone())


@app.post("/api/tasks", status_code=201)
def create_task(data: TaskIn, actor: str = Depends(require_owner)):
    with connect() as db:
        if not db.execute("SELECT id FROM opportunities WHERE id = ?", (data.opportunity_id,)).fetchone():
            raise HTTPException(404, "Opportunity not found")
        cur = db.execute("INSERT INTO tasks (opportunity_id, description, created_at) VALUES (?, ?, ?)",
                         (data.opportunity_id, data.description, now()))
        return row_dict(db.execute("SELECT * FROM tasks WHERE id = ?", (cur.lastrowid,)).fetchone())


@app.get("/api/tasks")
def list_tasks(actor: str = Depends(require_owner)):
    with connect() as db:
        return [row_dict(r) for r in db.execute("""
            SELECT tasks.*, opportunities.title AS opportunity_title, opportunities.platform
            FROM tasks JOIN opportunities ON opportunities.id = tasks.opportunity_id
            ORDER BY tasks.created_at DESC
        """).fetchall()]


@app.post("/api/tasks/{task_id}/approve")
def approve_task(task_id: int, actor: str = Depends(require_owner)):
    with connect() as db:
        row = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Task not found")
        if row["status"] != "pending_approval":
            raise HTTPException(409, "Only tasks awaiting approval can be approved")
        db.execute("UPDATE tasks SET status = 'approved', approved_at = ? WHERE id = ?", (now(), task_id))
        return row_dict(db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone())


@app.post("/api/tasks/{task_id}/complete")
def complete_task(task_id: int, actor: str = Depends(require_owner)):
    with connect() as db:
        row = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Task not found")
        if row["status"] != "approved":
            raise HTTPException(409, "A task must be approved before it can be marked complete")
        db.execute("UPDATE tasks SET status = 'completed', completed_at = ? WHERE id = ?", (now(), task_id))
        return row_dict(db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone())


@app.get("/api/rewards")
def list_rewards(actor: str = Depends(require_owner)):
    with connect() as db:
        return [row_dict(r) for r in db.execute("""
            SELECT rewards.*, opportunities.title AS opportunity_title
            FROM rewards LEFT JOIN opportunities ON opportunities.id = rewards.opportunity_id
            ORDER BY rewards.created_at DESC
        """).fetchall()]


@app.post("/api/rewards", status_code=201)
def create_reward(data: RewardIn, actor: str = Depends(require_owner)):
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

@app.get("/api/earnings")
def list_earnings(actor: str = Depends(require_owner)):
    with connect() as db:
        return [row_dict(r) for r in db.execute("""
            SELECT earnings_ledger.*, opportunities.title AS opportunity_title
            FROM earnings_ledger
            LEFT JOIN opportunities ON opportunities.id = earnings_ledger.opportunity_id
            ORDER BY earnings_ledger.created_at DESC, earnings_ledger.id DESC
        """).fetchall()]


@app.post("/api/earnings", status_code=201)
def create_earning(data: EarningsLedgerIn, actor: str = Depends(require_owner)):
    with connect() as db:
        if data.opportunity_id is not None and not db.execute(
            "SELECT id FROM opportunities WHERE id = ?", (data.opportunity_id,)
        ).fetchone():
            raise HTTPException(404, "Opportunity not found")
        timestamp = now()
        cur = db.execute("""
            INSERT INTO earnings_ledger
            (opportunity_id, amount, currency, state, reference, evidence, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (data.opportunity_id, data.amount, data.currency.upper(), data.state,
              data.reference.strip(), data.evidence.strip(), timestamp, timestamp))
        ledger_id = cur.lastrowid
        db.execute("""
            INSERT INTO earnings_ledger_events
            (ledger_id, actor, from_state, to_state, note, created_at)
            VALUES (?, ?, NULL, ?, ?, ?)
        """, (ledger_id, actor, data.state, "ثبت اولیه", timestamp))
        return row_dict(db.execute(
            "SELECT * FROM earnings_ledger WHERE id = ?", (ledger_id,)
        ).fetchone())


@app.patch("/api/earnings/{ledger_id}/state")
def update_earning_state(ledger_id: int, data: EarningsStateIn,
                         actor: str = Depends(require_owner)):
    allowed = {
        "estimated": {"earned", "pending"},
        "earned": {"pending", "withdrawable"},
        "pending": {"withdrawable"},
        "withdrawable": {"pending", "paid"},
        "paid": set(),
    }
    with connect() as db:
        row = db.execute(
            "SELECT * FROM earnings_ledger WHERE id = ?", (ledger_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(404, "Earning record not found")
        previous = row["state"]
        if data.state == previous:
            raise HTTPException(409, "Earning record already has this state")
        if data.state not in allowed[previous]:
            raise HTTPException(409, "This earning-state transition is not allowed")
        timestamp = now()
        db.execute("""
            UPDATE earnings_ledger SET state = ?, updated_at = ? WHERE id = ?
        """, (data.state, timestamp, ledger_id))
        db.execute("""
            INSERT INTO earnings_ledger_events
            (ledger_id, actor, from_state, to_state, note, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (ledger_id, actor, previous, data.state, data.note.strip(), timestamp))
        return row_dict(db.execute(
            "SELECT * FROM earnings_ledger WHERE id = ?", (ledger_id,)
        ).fetchone())


@app.get("/api/earnings/{ledger_id}/history")
def earning_history(ledger_id: int, actor: str = Depends(require_owner)):
    with connect() as db:
        if not db.execute(
            "SELECT id FROM earnings_ledger WHERE id = ?", (ledger_id,)
        ).fetchone():
            raise HTTPException(404, "Earning record not found")
        return [row_dict(r) for r in db.execute("""
            SELECT id, ledger_id, actor, from_state, to_state, note, created_at
            FROM earnings_ledger_events WHERE ledger_id = ?
            ORDER BY created_at, id
        """, (ledger_id,)).fetchall()]


@app.post("/api/opportunities/{opportunity_id}/evaluate")
def evaluate_opportunity(opportunity_id: int, data: OpportunityEvaluationIn,
                         actor: str = Depends(require_owner)):
    with connect() as db:
        opportunity = db.execute(
            "SELECT * FROM opportunities WHERE id = ?", (opportunity_id,)
        ).fetchone()
        source = db.execute(
            "SELECT * FROM sources WHERE id = ?", (data.source_id,)
        ).fetchone()
    if opportunity is None or source is None:
        raise HTTPException(404, "Opportunity or source not found.")
    opportunity_host = (urlparse(opportunity["url"]).hostname or "").casefold()
    source_host = (urlparse(source["url"]).hostname or "").casefold()
    if not opportunity_host or source_host != opportunity_host:
        raise HTTPException(409, "The reviewed source must belong to the same host as the opportunity.")
    category_map = {
        "game": "games_competitions", "skill": "games_competitions",
        "survey": "surveys_microtasks", "mobile": "other",
    }
    category = category_map.get(opportunity["category"], opportunity["category"])
    if category not in {"games_competitions", "surveys_microtasks",
                        "freelancing_services", "ai_content_products", "other"}:
        category = "other"
    try:
        candidate = OpportunityCandidate(
            title=opportunity["title"],
            category=category,
            source_status=source["status"],
            verification_status=opportunity["verification_status"],
            execution_mode=data.execution_mode,
            eligible_countries=tuple(json.loads(opportunity["eligible_countries"] or "[]")),
            excluded_countries=tuple(json.loads(opportunity["excluded_countries"] or "[]")),
            observed_at=opportunity["verified_at"] or "",
            reward_amount=data.reward_amount,
            reward_currency=data.reward_currency,
            estimated_cost=data.estimated_cost,
            payout_fee_fixed=data.payout_fee_fixed,
            payout_fee_percent=data.payout_fee_percent,
            conversion_fee_percent=data.conversion_fee_percent,
            minimum_withdrawal_amount=(
                opportunity["minimum_withdrawal_amount"]
                if opportunity["minimum_withdrawal_amount"] is not None
                and opportunity["withdrawal_currency"].upper() == data.reward_currency.upper()
                else None
            ),
            estimated_minutes=data.estimated_minutes,
            payment_probability=data.payment_probability,
            risk_score=data.risk_score,
            evidence=tuple(clean_list(data.evidence, "evidence")),
        )
        evaluation = evaluate_candidate(candidate, data.country)
        threshold_currency_mismatch = (
            opportunity["minimum_withdrawal_amount"] is not None
            and opportunity["withdrawal_currency"].upper() != data.reward_currency.upper()
        )
        evaluation["withdrawal_threshold_currency_mismatch"] = threshold_currency_mismatch
        if threshold_currency_mismatch:
            evaluation["execution_allowed"] = False
            evaluation["risk_flags"].append(
                "minimum withdrawal threshold uses a different currency; conversion is unknown"
            )
        if opportunity["status"] != "eligible":
            evaluation["execution_allowed"] = False
            evaluation["risk_flags"].append("opportunity status is not marked eligible")
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        raise HTTPException(422, f"Opportunity evaluation failed: {exc}")
    created_at = now()
    request_data = data.model_dump()
    with connect() as db:
        cursor = db.execute(
            """INSERT INTO evaluation_history
               (opportunity_id, source_id, country, execution_mode, request_json, result_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (opportunity_id, data.source_id, data.country.strip(),
             data.execution_mode, json.dumps(request_data, ensure_ascii=False),
             json.dumps(evaluation, ensure_ascii=False), created_at),
        )
        evaluation_id = cursor.lastrowid
    return {
        "evaluation_id": evaluation_id,
        "created_at": created_at,
        "opportunity_id": opportunity_id,
        "source_id": data.source_id,
        "title": opportunity["title"],
        "platform": opportunity["platform"],
        "source_status": source["status"],
        "opportunity_status": opportunity["status"],
        "evaluation": evaluation,
        "execution_note": "This is a readiness assessment only; no external platform action is executed.",
    }


@app.get("/api/opportunities/{opportunity_id}/evaluations")
def list_opportunity_evaluations(opportunity_id: int, actor: str = Depends(require_owner)):
    with connect() as db:
        if not db.execute("SELECT id FROM opportunities WHERE id = ?", (opportunity_id,)).fetchone():
            raise HTTPException(404, "Opportunity not found.")
        rows = db.execute(
            """SELECT id, opportunity_id, source_id, country, execution_mode,
                      request_json, result_json, created_at
               FROM evaluation_history
               WHERE opportunity_id = ?
               ORDER BY created_at DESC, id DESC""",
            (opportunity_id,),
        ).fetchall()
    return [{
        "evaluation_id": row["id"],
        "opportunity_id": row["opportunity_id"],
        "source_id": row["source_id"],
        "country": row["country"],
        "execution_mode": row["execution_mode"],        "request": json.loads(row["request_json"]),
        "evaluation": json.loads(row["result_json"]),
        "created_at": row["created_at"],
    } for row in rows]


@app.post("/api/discovery/rss", status_code=200)
def discover_rss_sources(data: RssDiscoveryIn, actor: str = Depends(require_owner)):
    try:
        adapter = PublicRssAdapter(
            adapter_id=data.adapter_id,
            display_name=data.display_name,
            feed_url=str(data.feed_url),
            category=data.category,
            allowed_domains=tuple(domain.strip().casefold() for domain in data.allowed_domains),
            max_items=data.max_items,
        )
        leads = adapter.discover()
    except (ValueError, OSError) as exc:
        raise HTTPException(422, f"RSS discovery rejected: {exc}")
    inserted = []
    duplicates = 0
    with connect() as db:
        for lead in leads:
            canonical_url = normalize_url(lead.url)
            # RSS candidates and manually registered opportunities share the
            # same conceptual URL namespace even though they live in separate
            # tables. Avoid re-importing an opportunity already in the main
            # opportunity catalog.
            existing_opportunity = db.execute(
                "SELECT id FROM opportunities WHERE url = ?", (canonical_url,)
            ).fetchone()
            if existing_opportunity:
                duplicates += 1
                continue
            try:
                cursor = db.execute(
                    """INSERT INTO sources
                       (name, url, category, terms_url, country_notes, payment_notes,
                        status, discovered_at, review_notes)
                       VALUES (?, ?, ?, ?, '', ?, 'pending', ?, '')""",
                    (lead.title[:160], canonical_url, lead.category,
                     lead.terms_url, lead.summary[:1000], lead.observed_at),
                )
                inserted.append({"id": cursor.lastrowid, "title": lead.title, "url": lead.url,
                                 "category": lead.category, "status": "pending"})
            except sqlite3.IntegrityError:
                duplicates += 1
    return {"adapter_id": data.adapter_id, "discovered_count": len(leads),
            "inserted_count": len(inserted), "duplicate_count": duplicates,
            "candidates": inserted, "review_required": True}


@app.post("/api/supervision/actions", status_code=201)
def request_supervised_action(data: SupervisedActionIn, actor: str = Depends(require_owner)):
    with connect() as db:
        opportunity = db.execute(
            "SELECT * FROM opportunities WHERE id = ?", (data.opportunity_id,)
        ).fetchone()
        source = db.execute(
            "SELECT * FROM sources WHERE id = ?", (data.source_id,)
        ).fetchone()
        if opportunity is None or source is None:
            raise HTTPException(404, "Opportunity or source not found.")
        if opportunity["status"] != "eligible" or opportunity["verification_status"] != "verified":
            raise HTTPException(409, "Opportunity must be eligible and manually verified.")
        if source["status"] != "approved":
            raise HTTPException(409, "Source must be manually approved.")
        verified_at = opportunity["verified_at"]
        if not verified_at:
            raise HTTPException(409, "Fresh verification evidence is required.")
        try:
            verified_time = datetime.fromisoformat(verified_at)
            age_seconds = (datetime.now(timezone.utc) - verified_time).total_seconds()
        except ValueError:
            raise HTTPException(409, "Verification timestamp is invalid.")
        if age_seconds < -300 or age_seconds > 30 * 24 * 60 * 60:
            raise HTTPException(409, "Verification is older than 30 days; review it again.")
    store = SQLiteSupervisionStore(DB_PATH)
    try:
        item = store.create(
            opportunity_id=data.opportunity_id, action=data.action,
            description=data.description, opportunity_eligible=True,
            source_approved=True, evidence_fresh=True, actor=actor,
        )
    except SupervisionError as exc:
        raise HTTPException(422, str(exc))
    return item.__dict__


@app.get("/api/supervision/actions")
def list_supervised_actions(status: Literal["pending_approval", "approved", "rejected", "completed", "cancelled"] | None = None,
                             actor: str = Depends(require_owner)):
    return [item.__dict__ for item in SQLiteSupervisionStore(DB_PATH).list(status)]


@app.post("/api/supervision/actions/{request_id}/approve")
def approve_supervised_action(request_id: str, actor: str = Depends(require_owner)):
    try:
        return SQLiteSupervisionStore(DB_PATH).approve(request_id, actor=actor).__dict__
    except SupervisionError as exc:
        raise HTTPException(409, str(exc))


@app.post("/api/supervision/actions/{request_id}/reject")
def reject_supervised_action(request_id: str, data: ActionDecisionIn, actor: str = Depends(require_owner)):
    try:
        return SQLiteSupervisionStore(DB_PATH).reject(request_id, actor=actor, reason=data.reason).__dict__
    except SupervisionError as exc:
        raise HTTPException(409, str(exc))


@app.post("/api/supervision/actions/{request_id}/complete")
def complete_supervised_action(request_id: str, data: ActionCompletionIn, actor: str = Depends(require_owner)):
    try:
        return SQLiteSupervisionStore(DB_PATH).complete(request_id, actor=actor, evidence=data.evidence).__dict__
    except SupervisionError as exc:
        raise HTTPException(409, str(exc))


@app.get("/api/supervision/actions/{request_id}/audit")
def supervised_action_audit(request_id: str, actor: str = Depends(require_owner)):
    store = SQLiteSupervisionStore(DB_PATH)
    if store.get(request_id) is None:
        raise HTTPException(404, "Action request not found.")
    return [event.__dict__ for event in store.audit_events(request_id)]


@app.get("/api/dashboard")
def dashboard(actor: str = Depends(require_owner)):
    with connect() as db:
        opportunities = db.execute("SELECT COUNT(*) FROM opportunities").fetchone()[0]
        tasks = db.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        awaiting = db.execute("SELECT COUNT(*) FROM tasks WHERE status = 'pending_approval'").fetchone()[0]
        paid = db.execute("SELECT COALESCE(SUM(amount), 0) FROM rewards WHERE status = 'paid'").fetchone()[0]
        pending = db.execute("SELECT COALESCE(SUM(amount), 0) FROM rewards WHERE status = 'pending'").fetchone()[0]
        earnings_totals = {}
        for currency_row in db.execute("SELECT DISTINCT currency FROM earnings_ledger").fetchall():
            currency = currency_row["currency"]
            earnings_totals[currency] = {
                item["state"]: round(item["total"], 2)
                for item in db.execute(
                    "SELECT state, COALESCE(SUM(amount), 0) AS total FROM earnings_ledger WHERE currency = ? GROUP BY state",
                    (currency,),
                ).fetchall()
            }
        return {"opportunities": opportunities, "tasks": tasks, "awaiting_approval": awaiting,
                "paid_total": round(paid, 2), "pending_total": round(pending, 2),
                "earnings_totals": earnings_totals}