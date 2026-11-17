from __future__ import annotations

import asyncio
import json
import os
import hmac
import hashlib
import ipaddress
import sqlite3
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from dataclasses import asdict
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Query, Depends, Header, UploadFile, File
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, HttpUrl

from autoearn.opportunities import normalize_url
from autoearn.supervision_store import SQLiteSupervisionStore
from autoearn.supervision import SupervisionError
from autoearn.rss import PublicRssAdapter
from autoearn.evaluator import OpportunityCandidate, evaluate_candidate
from autoearn.competitions import (
    AIProviderError, Competition, CompetitionAdapterRegistry, assess_competition, build_strategy,
)
from autoearn.task_suitability import TaskProfile, assess_task_suitability
from autoearn.ranking import rank_evaluations
from autoearn.discovery_ranking import prioritize_discovery_leads
from autoearn.tracks import get_track, infer_track_from_text, track_matches_category, tracks_for_category

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.getenv("AUTOEARN_DB", ROOT / "autoearn.db"))
OWNER_TOKEN = os.getenv("AUTOEARN_OWNER_TOKEN", "")
STATIC_DIR = ROOT / "static"
EVIDENCE_DIR = Path(os.getenv("AUTOEARN_EVIDENCE_DIR", ROOT / "private_evidence"))
MAX_EVIDENCE_BYTES = 5 * 1024 * 1024
DISCOVERY_FEED_MIN_INTERVAL_SECONDS = 60
EVIDENCE_TYPES = {
    "application/pdf": (b"%PDF-", ".pdf"),
    "image/png": (b"\\x89PNG\\r\\n\\x1a\\n", ".png"),
    "image/jpeg": (b"\\xff\\xd8\\xff", ".jpg"),
}
competition_adapters = CompetitionAdapterRegistry()


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.is_symlink():
        raise RuntimeError("Database path must not be a symbolic link")
    if os.name == "posix" and not DB_PATH.exists():
        try:
            descriptor = os.open(DB_PATH, os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600)
            os.close(descriptor)
        except FileExistsError:
            pass
    db = sqlite3.connect(DB_PATH)
    if os.name == "posix":
        os.chmod(DB_PATH, 0o600)
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
        CREATE TABLE IF NOT EXISTS discovery_feeds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            feed_url TEXT NOT NULL UNIQUE,
            category TEXT NOT NULL,
            allowed_domains TEXT NOT NULL,
            max_items INTEGER NOT NULL DEFAULT 30,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL,
            reviewed_at TEXT,
            last_checked_at TEXT,
            last_success_at TEXT,
            etag TEXT,
            last_modified TEXT,
            consecutive_failures INTEGER NOT NULL DEFAULT 0,
            total_checks INTEGER NOT NULL DEFAULT 0,
            total_successes INTEGER NOT NULL DEFAULT 0,
            last_error TEXT NOT NULL DEFAULT '',
            next_retry_at TEXT
        );
        CREATE TABLE IF NOT EXISTS discovery_leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_feed_id INTEGER REFERENCES discovery_feeds(id) ON DELETE SET NULL,
            source_name TEXT NOT NULL,
            title TEXT NOT NULL,
            url TEXT NOT NULL UNIQUE,
            category TEXT NOT NULL,
            summary TEXT NOT NULL DEFAULT '',
            terms_url TEXT NOT NULL DEFAULT '',
            observed_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            review_notes TEXT NOT NULL DEFAULT '',
            opportunity_id INTEGER REFERENCES opportunities(id) ON DELETE SET NULL,
            track_key TEXT NOT NULL DEFAULT '',
            track_review_status TEXT NOT NULL DEFAULT 'needs_review'
        );
        CREATE TABLE IF NOT EXISTS discovery_research (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER NOT NULL REFERENCES discovery_leads(id) ON DELETE CASCADE,
            country TEXT NOT NULL,
            country_status TEXT NOT NULL DEFAULT 'unknown',
            country_evidence_url TEXT NOT NULL DEFAULT '',
            payout_status TEXT NOT NULL DEFAULT 'unknown',
            payout_evidence_url TEXT NOT NULL DEFAULT '',
            ai_permission TEXT NOT NULL DEFAULT 'unknown',
            ai_evidence_url TEXT NOT NULL DEFAULT '',
            api_status TEXT NOT NULL DEFAULT 'unknown',
            api_evidence_url TEXT NOT NULL DEFAULT '',
            notes TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL,
            UNIQUE(lead_id, country)
        );
        CREATE INDEX IF NOT EXISTS idx_discovery_research_lead
            ON discovery_research(lead_id, country);
        CREATE TABLE IF NOT EXISTS discovery_scheduler (
            id INTEGER PRIMARY KEY CHECK(id = 1),
            enabled INTEGER NOT NULL DEFAULT 1,
            interval_minutes INTEGER NOT NULL DEFAULT 360,
            lease_until TEXT,
            lease_token TEXT NOT NULL DEFAULT '',
            last_started_at TEXT,
            last_completed_at TEXT,
            last_result_json TEXT NOT NULL DEFAULT '{}',
            last_error TEXT NOT NULL DEFAULT ''
        );
        INSERT OR IGNORE INTO discovery_scheduler (id, enabled, interval_minutes)
            VALUES (1, 1, 360);
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
        CREATE TABLE IF NOT EXISTS earnings_evidence (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ledger_id INTEGER NOT NULL REFERENCES earnings_ledger(id) ON DELETE CASCADE,
            stored_name TEXT NOT NULL UNIQUE,
            media_type TEXT NOT NULL,
            size_bytes INTEGER NOT NULL CHECK(size_bytes > 0 AND size_bytes <= 5242880),
            sha256 TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_earnings_evidence_ledger
            ON earnings_evidence(ledger_id, created_at, id);

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
        CREATE TABLE IF NOT EXISTS competitions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            url TEXT NOT NULL,
            rules_url TEXT NOT NULL,
            task_type TEXT NOT NULL,
            country TEXT NOT NULL,
            eligibility TEXT NOT NULL DEFAULT 'unknown',
            terms_verified INTEGER NOT NULL DEFAULT 0,
            automated_agents_allowed INTEGER NOT NULL DEFAULT 0,
            official_api INTEGER NOT NULL DEFAULT 0,
            prize_amount REAL,
            prize_currency TEXT NOT NULL DEFAULT 'EUR',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS competition_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            competition_id INTEGER NOT NULL REFERENCES competitions(id) ON DELETE CASCADE,
            plan_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_competition_plans_latest
            ON competition_plans(competition_id, created_at DESC, id DESC);
        CREATE TABLE IF NOT EXISTS competition_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            competition_id INTEGER NOT NULL REFERENCES competitions(id) ON DELETE CASCADE,
            mode TEXT NOT NULL,
            status TEXT NOT NULL,
            result_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS competition_adapter_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            adapter_id TEXT NOT NULL,
            requested_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_competition_adapter_requests_window
            ON competition_adapter_requests(adapter_id, requested_at);
        CREATE TABLE IF NOT EXISTS execution_control (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            paused INTEGER NOT NULL DEFAULT 1,
            updated_at TEXT NOT NULL,
            updated_by TEXT NOT NULL DEFAULT 'system',
            reason TEXT NOT NULL DEFAULT ''
        );
        INSERT OR IGNORE INTO execution_control (id, paused, updated_at, updated_by, reason)
            VALUES (1, 1, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'), 'system', 'Paused by default');
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
        lead_columns = {row["name"] for row in db.execute("PRAGMA table_info(discovery_leads)")}
        for name, definition in {"track_key": "TEXT NOT NULL DEFAULT ''", "track_review_status": "TEXT NOT NULL DEFAULT 'needs_review'"}.items():
            if name not in lead_columns:
                db.execute(f"ALTER TABLE discovery_leads ADD COLUMN {name} {definition}")
        scheduler_columns = {row["name"] for row in db.execute("PRAGMA table_info(discovery_scheduler)")}
        if "lease_token" not in scheduler_columns:
            db.execute("ALTER TABLE discovery_scheduler ADD COLUMN lease_token TEXT NOT NULL DEFAULT ''")
        feed_columns = {row["name"] for row in db.execute("PRAGMA table_info(discovery_feeds)")}
        feed_migrations = {
            "last_success_at": "TEXT",
            "etag": "TEXT",
            "last_modified": "TEXT",
            "consecutive_failures": "INTEGER NOT NULL DEFAULT 0",
            "total_checks": "INTEGER NOT NULL DEFAULT 0",
            "total_successes": "INTEGER NOT NULL DEFAULT 0",
            "next_retry_at": "TEXT",
        }
        for name, definition in feed_migrations.items():
            if name not in feed_columns:
                db.execute(f"ALTER TABLE discovery_feeds ADD COLUMN {name} {definition}")


async def _discovery_scheduler_loop() -> None:
    """Poll the durable scheduler; SQLite leases prevent duplicate workers."""
    while True:
        await asyncio.sleep(30)
        try:
            await asyncio.to_thread(_run_discovery_if_due)
        except Exception:
            # The durable scheduler row records failures; never kill the app loop.
            continue


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    scheduler_task = asyncio.create_task(_discovery_scheduler_loop())
    try:
        yield
    finally:
        scheduler_task.cancel()
        try:
            await scheduler_task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title="AutoEarn AI",
    description="Human-in-the-loop opportunity discovery and reward tracking.",
    version="0.1.0",
    lifespan=lifespan,
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    if request.url.path == "/" or request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; base-uri 'self'; form-action 'self'; "
        "frame-ancestors 'none'; object-src 'none'; "
        "script-src 'self'; style-src 'self'; img-src 'self' data:; "
        "connect-src 'self'",
    )
    return response



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
    withdrawal_currency: str = Field(default="USD", min_length=3, max_length=8)
    payout_methods: list[str] = Field(default_factory=list, max_length=30)


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

class DiscoveryFeedIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    feed_url: HttpUrl
    category: Literal["games_competitions", "surveys_microtasks", "freelancing_services", "ai_content_products", "other"]
    allowed_domains: list[str] = Field(min_length=1, max_length=10)
    max_items: int = Field(default=30, ge=1, le=50)


class DiscoveryLeadReviewIn(BaseModel):
    status: Literal["pending", "rejected"]
    notes: str = Field(default="", max_length=1000)


class DiscoveryTrackAssignmentIn(BaseModel):
    track_key: str = Field(default="", max_length=80)


class DiscoveryResearchIn(BaseModel):
    country: str = Field(min_length=2, max_length=80)
    country_status: Literal["unknown", "verified", "blocked"] = "unknown"
    country_evidence_url: str = Field(default="", max_length=500)
    payout_status: Literal["unknown", "verified", "unavailable"] = "unknown"
    payout_evidence_url: str = Field(default="", max_length=500)
    ai_permission: Literal["unknown", "allowed", "prohibited"] = "unknown"
    ai_evidence_url: str = Field(default="", max_length=500)
    api_status: Literal["unknown", "available", "unavailable"] = "unknown"
    api_evidence_url: str = Field(default="", max_length=500)
    notes: str = Field(default="", max_length=2000)


class DiscoveryFeedReviewIn(BaseModel):
    status: Literal["pending", "approved", "rejected"]


class DiscoverySchedulerUpdateIn(BaseModel):
    enabled: bool
    interval_minutes: int = Field(default=360, ge=60, le=1440)


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
    acceptance_probability: int | None = Field(default=None, ge=0, le=100)
    payout_reliability: int | None = Field(default=None, ge=0, le=100)
    supports_balance_accumulation: bool | None = None
    # Must be explicitly confirmed for the selected residence country; unknown is not supported.
    payout_supported: bool | None = None
    payout_route_configured: bool | None = None
    risk_score: int | None = Field(default=None, ge=0, le=100)
    evidence: list[str] = Field(default_factory=list, max_length=20)
    # Required for official-API readiness: explicit AI policy and task characteristics.
    ai_task_profile: dict[str, object] | None = None


class TaskSuitabilityIn(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    ai_permission: Literal["allowed", "prohibited", "unknown"] = "unknown"
    requires_physical_presence: bool = False
    requires_personal_experience: bool = False
    requires_identity_attestation: bool = False
    requires_captcha: bool = False
    requires_live_human_interaction: bool = False
    contains_sensitive_personal_data: bool = False
    repetitive_information_processing: bool = False
    output_is_objectively_verifiable: bool = False
    human_signoff_required: bool = True


class CompetitionIn(BaseModel):
    title: str = Field(min_length=2, max_length=160)
    url: HttpUrl
    rules_url: HttpUrl
    task_type: Literal["logic", "coding", "chess", "strategy", "general"] = "general"
    country: str = Field(min_length=2, max_length=80)
    eligibility: Literal["eligible", "ineligible", "unknown"] = "unknown"
    terms_verified: bool = False
    automated_agents_allowed: bool = False
    official_api: bool = False
    prize_amount: float | None = Field(default=None, ge=0)
    prize_currency: str = Field(default="EUR", min_length=3, max_length=8)


class CompetitionPlanIn(BaseModel):
    objective: str = Field(default="", max_length=1000)


class CompetitionSubmitIn(BaseModel):
    adapter_id: str = Field(min_length=2, max_length=80)
    payload: dict = Field(default_factory=dict)
    owner_confirmed: bool = False


class ExecutionControlIn(BaseModel):
    paused: bool
    reason: str = Field(default="", max_length=500)


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
    try:
        parsed = urlparse(value)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc) and not parsed.username and not parsed.password
    except ValueError:
        return False


def safe_public_https_evidence_url(value: str) -> bool:
    """Check URL shape and reject obvious local/private evidence destinations.

    This does not fetch the page or prove that its publisher is the platform.
    Owner review of the actual page and its policy remains mandatory.
    """
    try:
        parsed = urlparse(value)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            return False
        host = parsed.hostname.rstrip(".").casefold()
        if not host or host == "localhost" or host.endswith((".localhost", ".local", ".internal", ".lan")):
            return False
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            labels = host.split(".")
            if len(labels) < 2 or any(
                not label or len(label) > 63
                or not label[0].isalnum() or not label[-1].isalnum()
                or any(not (char.isalnum() or char == "-") for char in label)
                for label in labels
            ):
                return False
            # Reject dotted-quad lookalikes that are not valid IP addresses.
            if all(label.isdigit() for label in labels):
                return False
        else:
            if not address.is_global:
                return False
        # Accessing .port also detects malformed port syntax.
        _ = parsed.port
        return True
    except ValueError:
        return False


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
def list_opportunities(status: str | None = None, verification_status: Literal["pending", "verified", "rejected"] | None = None, q: str | None = Query(default=None, max_length=100), actor: str = Depends(require_owner)):
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
    with connect() as db:
        existing = db.execute("SELECT id FROM opportunities WHERE url = ?", (payload["url"],)).fetchone()
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
        except sqlite3.IntegrityError as exc:
            # The unique URL index is the concurrency-safe authority.
            # SQLite may roll back a trigger's competing insert together
            # with the failed statement, so inspect the constraint error too.
            existing = db.execute(
                "SELECT id FROM opportunities WHERE url = ?", (payload["url"],)
            ).fetchone()
            if existing or "opportunities.url" in str(exc):
                raise HTTPException(409, "This opportunity URL is already registered.")
            raise
        row = db.execute("SELECT * FROM opportunities WHERE id = ?", (cur.lastrowid,)).fetchone()
        return row_dict(row)


@app.get("/api/sources")
def list_sources(status: Literal["pending", "approved", "rejected"] | None = None, actor: str = Depends(require_owner)):
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
        # Serialize competing state transitions so each decision is based on
        # the latest committed state and the audit trail cannot fork.
        db.execute("BEGIN IMMEDIATE")
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


@app.post("/api/earnings/{ledger_id}/evidence", status_code=201)
def upload_earning_evidence(
    ledger_id: int,
    upload: UploadFile = File(...),
    actor: str = Depends(require_owner),
):
    allowed = EVIDENCE_TYPES.get(upload.content_type or "")
    if allowed is None:
        raise HTTPException(415, "Only PDF, PNG, and JPEG evidence files are accepted.")
    payload = upload.file.read(MAX_EVIDENCE_BYTES + 1)
    if not payload or len(payload) > MAX_EVIDENCE_BYTES:
        raise HTTPException(413, "Evidence file must be between 1 byte and 5 MiB.")
    magic, extension = allowed
    if not payload.startswith(magic):
        raise HTTPException(415, "File content does not match its declared evidence type.")
    digest = hashlib.sha256(payload).hexdigest()
    stored_name = f"{uuid.uuid4().hex}{extension}"
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    # Receipt files contain potentially sensitive financial information. Keep
    # the directory owner-only even when it already existed with loose modes.
    if os.name == "posix":
        os.chmod(EVIDENCE_DIR, 0o700)
    target = (EVIDENCE_DIR / stored_name).resolve()
    if target.parent != EVIDENCE_DIR.resolve():
        raise HTTPException(400, "Invalid evidence storage path.")
    with connect() as db:
        if not db.execute(
            "SELECT id FROM earnings_ledger WHERE id = ?", (ledger_id,)
        ).fetchone():
            raise HTTPException(404, "Earning record not found.")
        count = db.execute(
            "SELECT COUNT(*) FROM earnings_evidence WHERE ledger_id = ?", (ledger_id,)
        ).fetchone()[0]
        if count >= 10:
            raise HTTPException(409, "An earning record can have at most 10 evidence files.")
        file_descriptor = None
        try:
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
            file_descriptor = os.open(target, flags, 0o600)
            with os.fdopen(file_descriptor, "wb") as evidence_file:
                file_descriptor = None
                evidence_file.write(payload)
            cur = db.execute(
                """INSERT INTO earnings_evidence
                   (ledger_id, stored_name, media_type, size_bytes, sha256, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (ledger_id, stored_name, upload.content_type, len(payload), digest, now()),
            )
        except Exception:
            if file_descriptor is not None:
                os.close(file_descriptor)
            target.unlink(missing_ok=True)
            raise
        return {
            "id": cur.lastrowid, "ledger_id": ledger_id,
            "media_type": upload.content_type, "size_bytes": len(payload),
            "sha256": digest, "created_at": now(),
        }


@app.get("/api/earnings/{ledger_id}/evidence")
def list_earning_evidence(ledger_id: int, actor: str = Depends(require_owner)):
    with connect() as db:
        if not db.execute(
            "SELECT id FROM earnings_ledger WHERE id = ?", (ledger_id,)
        ).fetchone():
            raise HTTPException(404, "Earning record not found.")
        rows = db.execute(
            """SELECT id, ledger_id, media_type, size_bytes, sha256, created_at
               FROM earnings_evidence WHERE ledger_id = ? ORDER BY created_at, id""",
            (ledger_id,),
        ).fetchall()
        return [row_dict(row) for row in rows]


@app.get("/api/earnings/{ledger_id}/evidence/{evidence_id}")
def download_earning_evidence(
    ledger_id: int, evidence_id: int, actor: str = Depends(require_owner)
):
    with connect() as db:
        row = db.execute(
            """SELECT stored_name, media_type FROM earnings_evidence
               WHERE id = ? AND ledger_id = ?""",
            (evidence_id, ledger_id),
        ).fetchone()
        if row is None:
            raise HTTPException(404, "Evidence file not found.")
        path = (EVIDENCE_DIR / row["stored_name"]).resolve()
        if path.parent != EVIDENCE_DIR.resolve() or not path.is_file():
            raise HTTPException(404, "Evidence file is unavailable.")
        suffix = EVIDENCE_TYPES[row["media_type"]][1]
        return FileResponse(
            path, media_type=row["media_type"],
            filename=f"earning-evidence-{evidence_id}{suffix}",
            headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
        )


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


@app.post("/api/task-suitability/assess")
def assess_task_suitability_api(data: TaskSuitabilityIn, actor: str = Depends(require_owner)):
    """Assess AI suitability for a task; this never authorizes execution."""
    profile = TaskProfile(**data.model_dump())
    assessment = assess_task_suitability(profile)
    return {
        "title": profile.title,
        "suitability": assessment.suitability,
        "score": assessment.score,
        "reasons": list(assessment.reasons),
        "permitted_ai_role": assessment.permitted_ai_role,
        "execution_authorized": False,
        "disclaimer": "Suitability is a screening aid, not proof of platform permission or a guarantee of earnings.",
    }


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
            minimum_withdrawal_amount=opportunity["minimum_withdrawal_amount"],
            minimum_withdrawal_currency=opportunity["withdrawal_currency"],
            estimated_minutes=data.estimated_minutes,
            payment_probability=data.payment_probability,
            acceptance_probability=data.acceptance_probability,
            payout_reliability=data.payout_reliability,
            supports_balance_accumulation=data.supports_balance_accumulation,
            payout_supported=data.payout_supported,
            payout_route_configured=data.payout_route_configured,
            risk_score=data.risk_score,
            evidence=tuple(clean_list(data.evidence, "evidence")),
        )
        evaluation = evaluate_candidate(candidate, data.country)
        ai_task_assessment = None
        if data.ai_task_profile is not None:
            try:
                task_profile = TaskSuitabilityIn.model_validate(data.ai_task_profile)
                ai_assessment = assess_task_suitability(
                    TaskProfile(**task_profile.model_dump())
                )
                ai_task_assessment = {
                    "suitability": ai_assessment.suitability,
                    "score": ai_assessment.score,
                    "reasons": list(ai_assessment.reasons),
                    "permitted_ai_role": ai_assessment.permitted_ai_role,
                    "execution_authorized": False,
                }
            except (ValueError, TypeError) as exc:
                raise HTTPException(422, f"AI task profile is invalid: {exc}")
        if data.execution_mode == "official_api":
            if ai_task_assessment is None:
                evaluation["execution_allowed"] = False
                evaluation["risk_flags"].append(
                    "AI task profile and explicit AI permission are required for official-API readiness"
                )
            elif ai_task_assessment["suitability"] != "ai_draft_candidate":
                evaluation["execution_allowed"] = False
                evaluation["risk_flags"].append(
                    "AI task suitability is not cleared for bounded draft preparation"
                )
        evaluation["ai_task_assessment"] = ai_task_assessment
        evaluation["execution_authorized"] = False
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
        "execution_authorized": False,
        "execution_note": "This is a readiness assessment only; AI may prepare a bounded draft only when explicitly permitted and suitable. Human review and owner confirmation are still required; no external platform action is executed.",
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


@app.get("/api/opportunities/ranked")
def ranked_opportunities(
    country: str = Query(min_length=2, max_length=80),
    actor: str = Depends(require_owner),
):
    """Rank the latest evaluation per opportunity, separated by currency."""
    with connect() as db:
        rows = db.execute(
            """SELECT eh.id AS evaluation_id, eh.opportunity_id, eh.source_id,
                      eh.country, eh.execution_mode, eh.result_json, eh.created_at,
                      o.title, o.platform, o.url, o.category, o.status,
                      o.verification_status,
                      dr.country_status AS research_country_status,
                      dr.payout_status AS research_payout_status,
                      dr.ai_permission AS research_ai_permission,
                      dr.api_status AS research_api_status,
                      dr.updated_at AS research_checked_at,
                      dr.country_evidence_url AS research_country_evidence_url,
                      dr.payout_evidence_url AS research_payout_evidence_url,
                      dr.ai_evidence_url AS research_ai_evidence_url,
                      dr.api_evidence_url AS research_api_evidence_url
               FROM evaluation_history eh
               JOIN opportunities o ON o.id = eh.opportunity_id
               LEFT JOIN discovery_leads dl ON dl.opportunity_id = o.id
               LEFT JOIN discovery_research dr
                 ON dr.lead_id = dl.id AND lower(trim(dr.country)) = lower(trim(eh.country))
               WHERE lower(trim(eh.country)) = lower(trim(?))
                 AND eh.id = (
                    SELECT MAX(latest.id)
                    FROM evaluation_history latest
                    WHERE latest.opportunity_id = eh.opportunity_id
                      AND lower(trim(latest.country)) = lower(trim(eh.country))
                 )
               ORDER BY eh.id DESC""",
            (country.strip(),),
        ).fetchall()
    records = []
    for row in rows:
        try:
            evaluation = json.loads(row["result_json"])
        except (TypeError, json.JSONDecodeError):
            evaluation = {}
        records.append({
            "evaluation_id": row["evaluation_id"],
            "opportunity_id": row["opportunity_id"],
            "source_id": row["source_id"],
            "country": row["country"],
            "execution_mode": row["execution_mode"],
            "title": row["title"],
            "platform": row["platform"],
            "url": row["url"],
            "category": row["category"],
            "opportunity_status": row["status"],
            "verification_status": row["verification_status"],
            "created_at": row["created_at"],
            "research": {
                "country_status": row["research_country_status"] or "unknown",
                "payout_status": row["research_payout_status"] or "unknown",
                "ai_permission": row["research_ai_permission"] or "unknown",
                "api_status": row["research_api_status"] or "unknown",
                "checked_at": row["research_checked_at"],
                "country_evidence_url": row["research_country_evidence_url"] or "",
                "payout_evidence_url": row["research_payout_evidence_url"] or "",
                "ai_evidence_url": row["research_ai_evidence_url"] or "",
                "api_evidence_url": row["research_api_evidence_url"] or "",
            },
            "evaluation": evaluation,
        })
    ranked = rank_evaluations(records)
    ranked["country"] = country.strip()
    return ranked


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
            exists = db.execute(
                "SELECT id FROM opportunities WHERE url = ? UNION SELECT id FROM discovery_leads WHERE url = ? LIMIT 1",
                (canonical_url, canonical_url),
            ).fetchone()
            if exists:
                db.execute(
                    "UPDATE discovery_leads SET last_seen_at = ? WHERE url = ?",
                    (now(), canonical_url),
                )
                duplicates += 1
                continue
            try:
                track_key = str(getattr(lead, "track_key", "") or "").strip()
                if track_key and not track_matches_category(track_key, lead.category):
                    track_key = ""
                if not track_key:
                    track_key = infer_track_from_text(lead.title, lead.summary, lead.category)
                track_review_status = "matched" if track_key else "needs_review"
                cursor = db.execute(
                    """INSERT INTO discovery_leads
                       (source_feed_id, source_name, title, url, category, summary,
                        terms_url, observed_at, status, created_at, last_seen_at,
                        track_key, track_review_status)
                       VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?)""",
                    (data.display_name, lead.title[:160], canonical_url, lead.category,
                     lead.summary[:1000], lead.terms_url, lead.observed_at, now(), now(),
                     track_key, track_review_status),
                )
                inserted.append({"id": cursor.lastrowid, "title": lead.title,
                                 "url": lead.url, "category": lead.category,
                                 "status": "pending", "track_key": track_key,
                                 "track_review_status": track_review_status})
            except sqlite3.IntegrityError:
                duplicates += 1
    return {"adapter_id": data.adapter_id, "discovered_count": len(leads),
            "inserted_count": len(inserted), "duplicate_count": duplicates,
            "candidates": inserted, "review_required": True}


@app.get("/api/discovery/tracks")
def list_discovery_tracks(category: str = Query(min_length=2, max_length=80),
                          actor: str = Depends(require_owner)):
    """List only tracks compatible with a lead parent category."""
    return [{"key": track.key, "label": track.label,
             "execution_guidance": track.execution_guidance,
             "priority": track.priority,
             "description": track.description}
            for track in tracks_for_category(category)]


@app.put("/api/discovery/leads/{lead_id}/track")
def assign_discovery_track(lead_id: int, data: DiscoveryTrackAssignmentIn,
                           actor: str = Depends(require_owner)):
    """Persist a reviewed track assignment without approving or executing a lead."""
    with connect() as db:
        lead = db.execute("SELECT * FROM discovery_leads WHERE id = ?", (lead_id,)).fetchone()
        if lead is None:
            raise HTTPException(404, "Discovery lead not found.")
        key = data.track_key.strip()
        if key:
            track = get_track(key)
            if track is None:
                raise HTTPException(422, "Unknown opportunity track.")
            if track.parent_category != lead["category"]:
                raise HTTPException(422, "Selected track does not match the lead category.")
            review_status = "matched"
        else:
            review_status = "needs_review"
        db.execute(
            "UPDATE discovery_leads SET track_key = ?, track_review_status = ? WHERE id = ?",
            (key, review_status, lead_id),
        )
        result = db.execute("SELECT * FROM discovery_leads WHERE id = ?", (lead_id,)).fetchone()
    response = row_dict(result)
    response["execution_authorized"] = False
    return response


@app.get("/api/discovery/leads")
def list_discovery_leads(status: Literal["pending", "converted", "rejected"] | None = None,
                         actor: str = Depends(require_owner)):
    sql = "SELECT * FROM discovery_leads"
    params = ()
    if status:
        sql += " WHERE status = ?"
        params = (status,)
    sql += " ORDER BY last_seen_at DESC, id DESC"
    with connect() as db:
        return [row_dict(row) for row in db.execute(sql, params).fetchall()]


@app.get("/api/discovery/leads/prioritized")
def prioritized_discovery_leads(
    country: str = Query(default="Iran", min_length=2, max_length=80),
    actor: str = Depends(require_owner),
):
    """Return a research-first queue with the owner's saved country-specific review state."""
    normalized_country = country.strip()
    with connect() as db:
        rows = db.execute(
            """SELECT l.*, f.status AS feed_status,
                      f.total_checks, f.total_successes,
                      f.consecutive_failures, f.last_success_at,
                      dr.country_status AS research_country_status,
                      dr.payout_status AS research_payout_status,
                      dr.ai_permission AS research_ai_permission,
                      dr.api_status AS research_api_status,
                      dr.updated_at AS research_updated_at
               FROM discovery_leads l
               LEFT JOIN discovery_feeds f ON f.id = l.source_feed_id
               LEFT JOIN discovery_research dr
                 ON dr.lead_id = l.id AND lower(trim(dr.country)) = lower(trim(?))
               WHERE l.status = 'pending'
               ORDER BY l.last_seen_at DESC, l.id DESC""",
            (normalized_country,),
        ).fetchall()
    result = prioritize_discovery_leads([row_dict(row) for row in rows])
    for item in result["items"]:
        item["research_country"] = normalized_country
        item["research_status"] = {
            "country": item.pop("research_country_status", None) or "unknown",
            "payout": item.pop("research_payout_status", None) or "unknown",
            "ai_permission": item.pop("research_ai_permission", None) or "unknown",
            "api": item.pop("research_api_status", None) or "unknown",
        }
        item["research_updated_at"] = item.pop("research_updated_at", None)
        item["execution_authorized"] = False
    return result


@app.get("/api/discovery/leads/{lead_id}/research")
def get_discovery_research(lead_id: int, country: str = Query(min_length=2, max_length=80),
                           actor: str = Depends(require_owner)):
    with connect() as db:
        lead = db.execute("SELECT id FROM discovery_leads WHERE id = ?", (lead_id,)).fetchone()
        if lead is None:
            raise HTTPException(404, "Discovery lead not found.")
        row = db.execute(
            "SELECT * FROM discovery_research WHERE lead_id = ? AND country = ?",
            (lead_id, country.strip()),
        ).fetchone()
    if row is None:
        return {
            "lead_id": lead_id, "country": country.strip(),
            "country_status": "unknown", "country_evidence_url": "",
            "payout_status": "unknown", "payout_evidence_url": "",
            "ai_permission": "unknown", "ai_evidence_url": "",
            "api_status": "unknown", "api_evidence_url": "",
            "notes": "", "execution_authorized": False,
            "evidence_validation_note": "Only HTTPS URL shape and public-host checks are performed; page authenticity and contents require owner review.",
        }
    result = row_dict(row)
    result["execution_authorized"] = False
    result["evidence_validation_note"] = "Only HTTPS URL shape and public-host checks are performed; page authenticity and contents require owner review."
    return result


@app.put("/api/discovery/leads/{lead_id}/research")
def save_discovery_research(lead_id: int, data: DiscoveryResearchIn,
                            actor: str = Depends(require_owner)):
    fields = (
        ("country_status", data.country_status, data.country_evidence_url),
        ("payout_status", data.payout_status, data.payout_evidence_url),
        ("ai_permission", data.ai_permission, data.ai_evidence_url),
        ("api_status", data.api_status, data.api_evidence_url),
    )
    for field_name, status, evidence_url in fields:
        if status != "unknown":
            if not evidence_url or not safe_public_https_evidence_url(evidence_url):
                raise HTTPException(422, f"{field_name} requires a valid public HTTPS evidence URL.")
    for _, _, evidence_url in fields:
        if evidence_url and not safe_public_https_evidence_url(evidence_url):
            raise HTTPException(422, "Evidence URLs must use HTTPS and a public hostname.")
    with connect() as db:
        lead = db.execute("SELECT id FROM discovery_leads WHERE id = ?", (lead_id,)).fetchone()
        if lead is None:
            raise HTTPException(404, "Discovery lead not found.")
        db.execute(
            """INSERT INTO discovery_research
               (lead_id, country, country_status, country_evidence_url,
                payout_status, payout_evidence_url, ai_permission, ai_evidence_url,
                api_status, api_evidence_url, notes, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(lead_id, country) DO UPDATE SET
                country_status=excluded.country_status,
                country_evidence_url=excluded.country_evidence_url,
                payout_status=excluded.payout_status,
                payout_evidence_url=excluded.payout_evidence_url,
                ai_permission=excluded.ai_permission,
                ai_evidence_url=excluded.ai_evidence_url,
                api_status=excluded.api_status,
                api_evidence_url=excluded.api_evidence_url,
                notes=excluded.notes, updated_at=excluded.updated_at""",
            (lead_id, data.country.strip(), data.country_status, data.country_evidence_url.strip(),
             data.payout_status, data.payout_evidence_url.strip(), data.ai_permission,
             data.ai_evidence_url.strip(), data.api_status, data.api_evidence_url.strip(),
             data.notes.strip(), now()),
        )
        result = row_dict(db.execute(
            "SELECT * FROM discovery_research WHERE lead_id = ? AND country = ?",
            (lead_id, data.country.strip()),
        ).fetchone())
    result["execution_authorized"] = False
    result["evidence_validation_note"] = "Only HTTPS URL shape and public-host checks are performed; page authenticity and contents require owner review."
    return result


@app.patch("/api/discovery/leads/{lead_id}/review")
def review_discovery_lead(lead_id: int, data: DiscoveryLeadReviewIn,
                          actor: str = Depends(require_owner)):
    with connect() as db:
        row = db.execute("SELECT * FROM discovery_leads WHERE id = ?", (lead_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "Discovery lead not found.")
        if row["status"] == "converted":
            raise HTTPException(409, "A converted lead cannot be rejected.")
        db.execute(
            "UPDATE discovery_leads SET status = ?, review_notes = ? WHERE id = ?",
            (data.status, data.notes.strip(), lead_id),
        )
        return row_dict(db.execute(
            "SELECT * FROM discovery_leads WHERE id = ?", (lead_id,)
        ).fetchone())


@app.post("/api/discovery/leads/{lead_id}/promote", status_code=201)
def promote_discovery_lead(lead_id: int, actor: str = Depends(require_owner)):
    with connect() as db:
        lead = db.execute("SELECT * FROM discovery_leads WHERE id = ?", (lead_id,)).fetchone()
        if lead is None:
            raise HTTPException(404, "Discovery lead not found.")
        if lead["status"] == "rejected":
            raise HTTPException(409, "Rejected leads cannot be promoted.")
        if lead["opportunity_id"] is not None:
            existing = db.execute(
                "SELECT * FROM opportunities WHERE id = ?", (lead["opportunity_id"],)
            ).fetchone()
            if existing is not None:
                return {"lead": row_dict(lead), "opportunity": row_dict(existing), "already_promoted": True}
        host = (urlparse(lead["url"]).hostname or "").casefold()
        if not host:
            raise HTTPException(422, "Discovered lead URL has no valid hostname.")
        category_map = {
            "games_competitions": "game",
            "surveys_microtasks": "survey",
            "freelancing_services": "freelance",
            "ai_content_products": "digital_product",
            "other": "other",
        }
        try:
            cursor = db.execute(
                """INSERT INTO opportunities
                   (title, platform, url, category, reward_description, eligibility,
                    terms_url, status, score, notes, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 'discovered', 0, ?, ?)""",
                (lead["title"][:160], host[:100], lead["url"],
                 category_map.get(lead["category"], "other"),
                 lead["summary"][:500], "شرایط کشور، پاداش و پرداخت هنوز باید بررسی شود.",
                 lead["terms_url"], "کشف خودکار از منبع: " + lead["source_name"],
                 now()),
            )
        except sqlite3.IntegrityError:
            existing = db.execute(
                "SELECT * FROM opportunities WHERE url = ?", (lead["url"],)
            ).fetchone()
            if existing is None:
                raise HTTPException(409, "Could not promote this discovery lead.")
            opportunity_id = existing["id"]
        else:
            opportunity_id = cursor.lastrowid
        db.execute(
            "UPDATE discovery_leads SET status = 'converted', opportunity_id = ? WHERE id = ?",
            (opportunity_id, lead_id),
        )
        opportunity = db.execute(
            "SELECT * FROM opportunities WHERE id = ?", (opportunity_id,)
        ).fetchone()
        updated_lead = db.execute(
            "SELECT * FROM discovery_leads WHERE id = ?", (lead_id,)
        ).fetchone()
        return {"lead": row_dict(updated_lead), "opportunity": row_dict(opportunity),
                "already_promoted": False}


@app.post("/api/discovery/feeds", status_code=201)
def create_discovery_feed(data: DiscoveryFeedIn, actor: str = Depends(require_owner)):
    feed_url = normalize_url(str(data.feed_url))
    parsed = urlparse(feed_url)
    host = (parsed.hostname or "").casefold()
    domains = [item.strip().casefold() for item in data.allowed_domains]
    if parsed.scheme != "https" or not host or parsed.username or parsed.password:
        raise HTTPException(422, "Discovery feed must use a public HTTPS URL without credentials.")
    if parsed.port not in (None, 443):
        raise HTTPException(422, "Discovery feed must use the standard HTTPS port 443.")
    if host not in domains:
        raise HTTPException(422, "The feed hostname must exactly match one allowed domain.")
    if len(set(domains)) != len(domains) or any(
        not domain or domain.startswith(".") or domain.endswith(".")
        or "*" in domain or "/" in domain or ":" in domain
        for domain in domains
    ):
        raise HTTPException(422, "Allowed domains must be unique exact hostnames; wildcards are not accepted.")
    with connect() as db:
        try:
            cursor = db.execute(
                """INSERT INTO discovery_feeds
                   (name, feed_url, category, allowed_domains, max_items, status, created_at)
                   VALUES (?, ?, ?, ?, ?, 'pending', ?)""",
                (data.name.strip(), feed_url, data.category,
                 json.dumps(domains), data.max_items, now()),
            )
        except sqlite3.IntegrityError:
            raise HTTPException(409, "This discovery feed is already registered.")
        row = db.execute("SELECT * FROM discovery_feeds WHERE id = ?",
                         (cursor.lastrowid,)).fetchone()
        item = row_dict(row)
        item["allowed_domains"] = json.loads(item["allowed_domains"] or "[]")
        return item


@app.get("/api/discovery/feeds")
def list_discovery_feeds(status: Literal["pending", "approved", "rejected"] | None = None,
                         actor: str = Depends(require_owner)):
    sql = "SELECT * FROM discovery_feeds"
    params = ()
    if status:
        sql += " WHERE status = ?"
        params = (status,)
    sql += " ORDER BY created_at DESC, id DESC"
    with connect() as db:
        rows = db.execute(sql, params).fetchall()
    result = []
    for row in rows:
        item = row_dict(row)
        item["allowed_domains"] = json.loads(item["allowed_domains"] or "[]")
        result.append(item)
    return result


@app.patch("/api/discovery/feeds/{feed_id}/review")
def review_discovery_feed(feed_id: int, data: DiscoveryFeedReviewIn,
                          actor: str = Depends(require_owner)):
    with connect() as db:
        row = db.execute("SELECT * FROM discovery_feeds WHERE id = ?", (feed_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "Discovery feed not found.")
        reviewed_at = now() if data.status != "pending" else None
        db.execute(
            "UPDATE discovery_feeds SET status = ?, reviewed_at = ? WHERE id = ?",
            (data.status, reviewed_at, feed_id),
        )
        updated = db.execute("SELECT * FROM discovery_feeds WHERE id = ?", (feed_id,)).fetchone()
        item = row_dict(updated)
        item["allowed_domains"] = json.loads(item["allowed_domains"] or "[]")
        return item


def _run_approved_discovery_batch():
    with connect() as db:
        feeds = db.execute(
            """SELECT * FROM discovery_feeds WHERE status = 'approved'
               ORDER BY id ASC LIMIT 25"""
        ).fetchall()
    feed_results = []
    inserted_count = 0
    duplicate_count = 0
    successful_feeds = 0
    for feed in feeds:
        feed_id = feed["id"]
        next_retry_at = feed["next_retry_at"]
        if next_retry_at:
            try:
                retry_time = datetime.fromisoformat(next_retry_at)
                if retry_time.tzinfo is None:
                    retry_time = retry_time.replace(tzinfo=timezone.utc)
                retry_delay = (retry_time - datetime.now(timezone.utc)).total_seconds()
                if retry_delay > 0:
                    feed_results.append({
                        "feed_id": feed_id, "name": feed["name"],
                        "status": "backoff", "inserted": 0, "duplicates": 0,
                        "retry_after_seconds": max(1, int(retry_delay)),
                    })
                    continue
            except (TypeError, ValueError):
                # A malformed legacy retry timestamp must not disable a feed.
                pass
        last_checked_at = feed["last_checked_at"]
        if last_checked_at:
            try:
                previous_check = datetime.fromisoformat(last_checked_at)
                if previous_check.tzinfo is None:
                    previous_check = previous_check.replace(tzinfo=timezone.utc)
                elapsed = (datetime.now(timezone.utc) - previous_check).total_seconds()
                if 0 <= elapsed < DISCOVERY_FEED_MIN_INTERVAL_SECONDS:
                    feed_results.append({
                        "feed_id": feed_id, "name": feed["name"],
                        "status": "rate_limited", "inserted": 0, "duplicates": 0,
                        "retry_after_seconds": max(
                            1, int(DISCOVERY_FEED_MIN_INTERVAL_SECONDS - elapsed)
                        ),
                    })
                    continue
            except (TypeError, ValueError):
                # A malformed legacy timestamp must not permanently disable a feed.
                pass
        try:
            adapter = PublicRssAdapter(
                adapter_id=f"stored-feed-{feed_id}",
                display_name=feed["name"],
                feed_url=feed["feed_url"],
                category=feed["category"],
                allowed_domains=tuple(json.loads(feed["allowed_domains"] or "[]")),
                max_items=feed["max_items"],
                etag=feed["etag"],
                last_modified=feed["last_modified"],
            )
            leads = adapter.discover()
            feed_inserted = 0
            feed_duplicates = 0
            with connect() as db:
                for lead in leads:
                    canonical_url = normalize_url(lead.url)
                    exists = db.execute(
                        "SELECT id FROM opportunities WHERE url = ? UNION SELECT id FROM discovery_leads WHERE url = ? LIMIT 1",
                        (canonical_url, canonical_url),
                    ).fetchone()
                    if exists:
                        db.execute(
                            "UPDATE discovery_leads SET last_seen_at = ? WHERE url = ?",
                            (now(), canonical_url),
                        )
                        feed_duplicates += 1
                        continue
                    try:
                        db.execute(
                            """INSERT INTO discovery_leads
                               (source_feed_id, source_name, title, url, category, summary,
                                terms_url, observed_at, status, created_at, last_seen_at)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)""",
                            (feed_id, feed["name"], lead.title[:160], canonical_url,
                             lead.category, lead.summary[:1000], lead.terms_url,
                             lead.observed_at, now(), now()),
                        )
                        feed_inserted += 1
                    except sqlite3.IntegrityError:
                        feed_duplicates += 1
                db.execute(
                    "UPDATE discovery_feeds SET last_checked_at = ?, last_success_at = ?, etag = ?, last_modified = ?, consecutive_failures = 0, total_checks = total_checks + 1, total_successes = total_successes + 1, last_error = '', next_retry_at = NULL WHERE id = ?",
                    (now(), now(), adapter.etag, adapter.last_modified, feed_id),
                )
            successful_feeds += 1
            inserted_count += feed_inserted
            duplicate_count += feed_duplicates
            feed_results.append({
                "feed_id": feed_id, "name": feed["name"],
                "status": "not_modified" if adapter.not_modified else "ok",
                "discovered": len(leads), "inserted": feed_inserted,
                "duplicates": feed_duplicates,
            })
        except Exception as exc:
            # One malformed or unavailable feed must not abort the whole batch.
            message = f"{type(exc).__name__}: {exc}"[:500]
            with connect() as db:
                failure_count = int(feed["consecutive_failures"] or 0) + 1
                backoff_seconds = min(21600, 60 * (2 ** min(failure_count - 1, 8)))
                retry_at = (datetime.now(timezone.utc) + timedelta(seconds=backoff_seconds)).isoformat()
                db.execute(
                    """UPDATE discovery_feeds
                       SET last_checked_at = ?, consecutive_failures = ?,
                           total_checks = total_checks + 1, last_error = ?,
                           next_retry_at = ?
                       WHERE id = ?""",
                    (now(), failure_count, message, retry_at, feed_id),
                )
            feed_results.append({
                "feed_id": feed_id, "name": feed["name"], "status": "error",
                "error": message,
            })
    return {
        "checked_at": now(), "approved_feed_count": len(feeds),
        "successful_feed_count": successful_feeds,
        "inserted_count": inserted_count, "duplicate_count": duplicate_count,
        "feeds": feed_results,
        "review_required": True,
        "note": "All discovered items remain pending for owner review; no platform action was taken.",
    }



def _acquire_discovery_lease(*, force: bool = False) -> str | None:
    """Acquire a fenced lease; each owner gets a unique token."""
    current = datetime.now(timezone.utc)
    token = uuid.uuid4().hex
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        state = db.execute("SELECT * FROM discovery_scheduler WHERE id = 1").fetchone()
        if state is None:
            db.execute(
                "INSERT INTO discovery_scheduler (id, enabled, interval_minutes) VALUES (1, 1, 360)"
            )
            state = db.execute("SELECT * FROM discovery_scheduler WHERE id = 1").fetchone()
        lease_until = state["lease_until"]
        if lease_until:
            try:
                if datetime.fromisoformat(lease_until) > current:
                    return None
            except ValueError:
                pass
        if not force:
            if not state["enabled"]:
                return None
            if state["last_completed_at"]:
                try:
                    completed = datetime.fromisoformat(state["last_completed_at"])
                    if completed.tzinfo is None:
                        completed = completed.replace(tzinfo=timezone.utc)
                    if current - completed < timedelta(minutes=state["interval_minutes"]):
                        return None
                except ValueError:
                    pass
        lease = (current + timedelta(minutes=30)).isoformat()
        db.execute(
            "UPDATE discovery_scheduler SET lease_until = ?, lease_token = ?, last_started_at = ?, last_error = '' WHERE id = 1",
            (lease, token, current.isoformat()),
        )
    return token


def _finish_discovery_lease(lease_token: str, result: dict | None = None,
                            error: str = "") -> bool:
    """Finish only the lease still owned by this worker (fencing token)."""
    with connect() as db:
        cursor = db.execute(
            """UPDATE discovery_scheduler
               SET lease_until = NULL, lease_token = '', last_completed_at = ?,
                   last_result_json = ?, last_error = ?
               WHERE id = 1 AND lease_token = ?""",
            (now(), json.dumps(result or {}, ensure_ascii=False), error[:500], lease_token),
        )
        return cursor.rowcount == 1


def _run_discovery_once(*, force: bool = False) -> dict | None:
    lease_token = _acquire_discovery_lease(force=force)
    if lease_token is None:
        return None
    try:
        result = _run_approved_discovery_batch()
        if not _finish_discovery_lease(lease_token, result=result):
            # A newer worker owns the scheduler now. Do not report this stale
            # worker's batch as the scheduler's completed result.
            return None
        return result
    except Exception as exc:
        _finish_discovery_lease(lease_token, error=str(exc))
        raise


def _run_discovery_if_due() -> bool:
    try:
        return _run_discovery_once(force=False) is not None
    except Exception:
        return False


@app.get("/api/discovery/health")
def get_discovery_health(actor: str = Depends(require_owner)):
    """Summarize approved-feed reliability without fetching any external URL."""
    current = datetime.now(timezone.utc)
    with connect() as db:
        feeds = db.execute(
            """SELECT id, name, feed_url, status, last_checked_at, last_success_at,
                      consecutive_failures, total_checks, total_successes, last_error
               FROM discovery_feeds ORDER BY status DESC, name COLLATE NOCASE"""
        ).fetchall()
        interval = db.execute(
            "SELECT interval_minutes FROM discovery_scheduler WHERE id = 1"
        ).fetchone()
    stale_after = max(120, (interval["interval_minutes"] if interval else 360) * 2)
    items = []
    counts = {"approved": 0, "healthy": 0, "error": 0, "stale": 0, "never_checked": 0,
              "pending_review": 0, "rejected": 0}
    for feed in feeds:
        status = feed["status"]
        if status != "approved":
            counts["pending_review" if status == "pending" else "rejected"] += 1
            health = "not_active"
        else:
            counts["approved"] += 1
            checked = feed["last_checked_at"]
            if not checked:
                health = "never_checked"
            elif feed["last_error"]:
                health = "error"
            else:
                try:
                    checked_at = datetime.fromisoformat(checked)
                    if checked_at.tzinfo is None:
                        checked_at = checked_at.replace(tzinfo=timezone.utc)
                    age_minutes = (current - checked_at).total_seconds() / 60
                    health = "stale" if age_minutes > stale_after else "healthy"
                except ValueError:
                    health = "stale"
            if health in counts:
                counts[health] += 1
        items.append({
            "id": feed["id"], "name": feed["name"], "url": feed["feed_url"],
            "review_status": status, "health": health,
            "last_checked_at": feed["last_checked_at"],
            "last_success_at": feed["last_success_at"],
            "consecutive_failures": feed["consecutive_failures"],
            "total_checks": feed["total_checks"],
            "total_successes": feed["total_successes"],
            "reliability_percent": round(100 * feed["total_successes"] / feed["total_checks"], 1) if feed["total_checks"] else None,
            "reliability_sample": "limited" if feed["total_checks"] < 5 else "established",
            "last_error": feed["last_error"],
        })
    return {"checked_at": current.isoformat(), "stale_after_minutes": stale_after,
            "counts": counts, "feeds": items}


@app.get("/api/discovery/scheduler")
def get_discovery_scheduler(actor: str = Depends(require_owner)):
    with connect() as db:
        state = db.execute("SELECT * FROM discovery_scheduler WHERE id = 1").fetchone()
        approved = db.execute(
            "SELECT COUNT(*) AS count FROM discovery_feeds WHERE status = 'approved'"
        ).fetchone()["count"]
    if state is None:
        raise HTTPException(503, "Discovery scheduler is not initialized.")
    interval = state["interval_minutes"]
    next_run = None
    if state["enabled"]:
        if state["last_completed_at"]:
            try:
                completed = datetime.fromisoformat(state["last_completed_at"])
                if completed.tzinfo is None:
                    completed = completed.replace(tzinfo=timezone.utc)
                next_run = (completed + timedelta(minutes=interval)).isoformat()
            except ValueError:
                next_run = now()
        else:
            next_run = now()
    try:
        last_result = json.loads(state["last_result_json"] or "{}")
    except json.JSONDecodeError:
        last_result = {}
    return {
        "enabled": bool(state["enabled"]),
        "interval_minutes": interval,
        "approved_feed_count": approved,
        "lease_until": state["lease_until"],
        "last_started_at": state["last_started_at"],
        "last_completed_at": state["last_completed_at"],
        "last_result": last_result,
        "last_error": state["last_error"],
        "next_run_at": next_run,
    }


@app.patch("/api/discovery/scheduler")
def update_discovery_scheduler(data: DiscoverySchedulerUpdateIn,
                               actor: str = Depends(require_owner)):
    with connect() as db:
        db.execute(
            "UPDATE discovery_scheduler SET enabled = ?, interval_minutes = ? WHERE id = 1",
            (1 if data.enabled else 0, data.interval_minutes),
        )
    return get_discovery_scheduler(actor)


@app.post("/api/discovery/run")
def run_approved_discovery(actor: str = Depends(require_owner)):
    try:
        result = _run_discovery_once(force=True)
    except Exception as exc:
        raise HTTPException(502, f"Discovery run failed: {str(exc)[:300]}")
    if result is None:
        raise HTTPException(409, "A discovery scan is already running; try again shortly.")
    return result


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


def competition_from_row(row, allowed_actions=()):
    return Competition(
        competition_id=row["id"], title=row["title"], url=row["url"],
        rules_url=row["rules_url"], task_type=row["task_type"],
        country=row["country"], eligibility=row["eligibility"],
        terms_verified=bool(row["terms_verified"]),
        automated_agents_allowed=bool(row["automated_agents_allowed"]),
        official_api=bool(row["official_api"]),
        allowed_actions=tuple(allowed_actions),
    )


@app.post("/api/competitions", status_code=201)
def create_competition(data: CompetitionIn, actor: str = Depends(require_owner)):
    payload = data.model_dump()
    payload["url"] = normalize_url(str(payload["url"]))
    payload["rules_url"] = normalize_url(str(payload["rules_url"]))
    if not safe_url(payload["url"]) or not safe_url(payload["rules_url"]):
        raise HTTPException(422, "Competition and rules URLs must use safe HTTP/HTTPS addresses.")
    if urlparse(payload["url"]).scheme != "https" or urlparse(payload["rules_url"]).scheme != "https":
        raise HTTPException(422, "Competition and rules pages must use HTTPS.")
    with connect() as db:
        cur = db.execute("""
            INSERT INTO competitions
            (title, url, rules_url, task_type, country, eligibility, terms_verified,
             automated_agents_allowed, official_api, prize_amount, prize_currency, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            payload["title"].strip(), payload["url"], payload["rules_url"],
            payload["task_type"], payload["country"].strip(), payload["eligibility"],
            int(payload["terms_verified"]), int(payload["automated_agents_allowed"]),
            int(payload["official_api"]), payload["prize_amount"],
            payload["prize_currency"].upper(), now(),
        ))
        row = db.execute("SELECT * FROM competitions WHERE id = ?", (cur.lastrowid,)).fetchone()
        return row_dict(row)


@app.get("/api/competitions")
def list_competitions(actor: str = Depends(require_owner)):
    with connect() as db:
        rows = db.execute("SELECT * FROM competitions ORDER BY created_at DESC, id DESC").fetchall()
        return [row_dict(row) for row in rows]


@app.post("/api/competitions/{competition_id}/plan")
def plan_competition(competition_id: int, data: CompetitionPlanIn,
                     actor: str = Depends(require_owner)):
    with connect() as db:
        row = db.execute("SELECT * FROM competitions WHERE id = ?", (competition_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "Competition not found.")
        try:
            plan = build_strategy(competition_id, row["task_type"], data.objective)
        except AIProviderError as exc:
            raise HTTPException(502, str(exc))
        except ValueError as exc:
            raise HTTPException(422, str(exc))
        plan_data = asdict(plan)
        created_at = now()
        db.execute(
            "INSERT INTO competition_plans (competition_id, plan_json, created_at) VALUES (?, ?, ?)",
            (competition_id, json.dumps(plan_data, ensure_ascii=False), created_at),
        )
    return {"plan": plan_data, "created_at": created_at,
            "note": "این نسخه از برنامه‌ریز پایه و شفاف استفاده می‌کند؛ هنوز مدل زبانی خارجی یا عامل مسابقهٔ واقعی متصل نشده است."}


@app.post("/api/competitions/{competition_id}/dry-run")
def dry_run_competition(competition_id: int, actor: str = Depends(require_owner)):
    with connect() as db:
        row = db.execute("SELECT * FROM competitions WHERE id = ?", (competition_id,)).fetchone()
        plan_row = db.execute(
            "SELECT plan_json FROM competition_plans WHERE competition_id = ? ORDER BY created_at DESC, id DESC LIMIT 1",
            (competition_id,),
        ).fetchone()
        if row is None:
            raise HTTPException(404, "Competition not found.")
        if plan_row is None:
            raise HTTPException(409, "Create an agent strategy before running a dry-run.")
        plan = json.loads(plan_row["plan_json"])
        competition_host = (urlparse(row["url"]).hostname or "").casefold()
        matching_manifest = next(
            (item for item in competition_adapters.list_manifests()
             if item.exact_host == competition_host),
            None,
        )
        allowed_actions = matching_manifest.allowed_actions if matching_manifest else ()
        readiness = assess_competition(competition_from_row(row, allowed_actions))
        result = {
            "status": "dry_run_only",
            "external_submission": False,
            "strategy_provider": plan["provider"],
            "strategy_steps_checked": len(plan["steps"]),
            "readiness": readiness.ready,
            "blockers": list(readiness.blockers),
            "message": "تمرین آزمایشی فقط برنامه و پیش‌نیازها را بررسی کرد؛ هیچ ورودی به مسابقه ارسال نشد.",
        }
        created_at = now()
        db.execute(
            "INSERT INTO competition_attempts (competition_id, mode, status, result_json, created_at) VALUES (?, 'dry_run', ?, ?, ?)",
            (competition_id, result["status"], json.dumps(result, ensure_ascii=False), created_at),
        )
    return result


@app.get("/api/execution-control")
def get_execution_control(actor: str = Depends(require_owner)):
    with connect() as db:
        row = db.execute(
            "SELECT paused, updated_at, updated_by, reason FROM execution_control WHERE id = 1"
        ).fetchone()
    if row is None:
        return {"paused": True, "updated_at": None, "updated_by": "system",
                "reason": "Paused by default"}
    return {"paused": bool(row["paused"]), "updated_at": row["updated_at"],
            "updated_by": row["updated_by"], "reason": row["reason"]}


@app.patch("/api/execution-control")
def update_execution_control(data: ExecutionControlIn,
                             actor: str = Depends(require_owner)):
    with connect() as db:
        db.execute(
            """UPDATE execution_control
               SET paused = ?, updated_at = ?, updated_by = ?, reason = ?
               WHERE id = 1""",
            (int(data.paused), now(), actor, data.reason.strip()),
        )
        row = db.execute(
            "SELECT paused, updated_at, updated_by, reason FROM execution_control WHERE id = 1"
        ).fetchone()
    return {"paused": bool(row["paused"]), "updated_at": row["updated_at"],
            "updated_by": row["updated_by"], "reason": row["reason"]}


@app.post("/api/competitions/{competition_id}/submit")
def submit_competition_entry(competition_id: int, data: CompetitionSubmitIn,
                             actor: str = Depends(require_owner)):
    if not data.owner_confirmed:
        raise HTTPException(403, "Explicit owner confirmation is required.")
    manifest = competition_adapters.get_manifest(data.adapter_id)
    if manifest is None:
        raise HTTPException(409, "No approved official competition adapter is installed for this platform.")
    adapter_limit = int(getattr(manifest, "requests_per_minute", 10))
    if adapter_limit < 1 or adapter_limit > 600:
        raise HTTPException(409, "Adapter declares an invalid request limit.")
    adapter_error = None
    result = None
    with connect() as db:
        row = db.execute("SELECT * FROM competitions WHERE id = ?", (competition_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "Competition not found.")
        competition = competition_from_row(row, manifest.allowed_actions)
        readiness = assess_competition(competition)
        if not readiness.ready:
            raise HTTPException(409, {"message": "Competition is not ready for automated entry.", "blockers": list(readiness.blockers)})
        # Serialize the pause check and durable rate reservation with owner
        # pause updates. The write lock stays held until the adapter call and
        # audit event finish, so a successful pause waits for in-flight work.
        db.execute("BEGIN IMMEDIATE")
        control = db.execute(
            "SELECT paused FROM execution_control WHERE id = 1"
        ).fetchone()
        if control is None or control["paused"]:
            raise HTTPException(423, "Global emergency pause is active; external submissions are blocked.")
        requested_at = datetime.now(timezone.utc)
        cutoff = (requested_at - timedelta(seconds=60)).isoformat()
        db.execute(
            "DELETE FROM competition_adapter_requests WHERE requested_at < ?",
            (cutoff,),
        )
        recent_requests = db.execute(
            """SELECT COUNT(*) FROM competition_adapter_requests
               WHERE adapter_id = ? AND requested_at >= ?""",
            (data.adapter_id, cutoff),
        ).fetchone()[0]
        if recent_requests >= adapter_limit:
            raise HTTPException(429, "Persistent adapter rate limit exceeded; wait before submitting again.")
        timestamp = requested_at.isoformat()
        db.execute(
            "INSERT INTO competition_adapter_requests (adapter_id, requested_at) VALUES (?, ?)",
            (data.adapter_id, timestamp),
        )
        # Write-ahead audit: persist the attempt intent before invoking an
        # external, non-idempotent API. If the process crashes during the
        # network call, history still shows an unresolved "submitting" record.
        intent = {
            "status": "submitting",
            "external_submission": "unknown",
            "message": "Submission started; verify the remote platform if no final result is recorded.",
        }
        attempt_cursor = db.execute(
            "INSERT INTO competition_attempts (competition_id, mode, status, result_json, created_at) VALUES (?, 'official_api', 'submitting', ?, ?)",
            (competition_id, json.dumps(intent, ensure_ascii=False), now()),
        )
        attempt_id = attempt_cursor.lastrowid
        db.commit()

        # Reacquire the write lock after persisting intent. If an emergency
        # pause won the gap, mark the intent blocked; otherwise keep the lock
        # through the adapter call so a successful pause waits for in-flight
        # external work to finish.
        db.execute("BEGIN IMMEDIATE")
        control = db.execute(
            "SELECT paused FROM execution_control WHERE id = 1"
        ).fetchone()
        if control is None or control["paused"]:
            blocked = {
                "status": "blocked", "external_submission": False,
                "message": "Emergency pause became active before the adapter call.",
            }
            db.execute(
                "UPDATE competition_attempts SET status = 'blocked', result_json = ? WHERE id = ?",
                (json.dumps(blocked, ensure_ascii=False), attempt_id),
            )
            db.commit()
            raise HTTPException(423, "Global emergency pause became active; external submission was blocked.")

        try:
            receipt = competition_adapters.submit(
                data.adapter_id, competition, data.payload, owner_confirmed=True
            )
        except Exception as exc:
            # The remote outcome may be ambiguous. Preserve the reservation
            # and the already committed intent; never auto-retry this action.
            adapter_error = type(exc).__name__
            failure = {
                "status": "failed", "error_type": adapter_error,
                "external_submission": "unknown",
                "message": "Adapter failed; verify the remote platform before any manual retry.",
            }
            db.execute(
                "UPDATE competition_attempts SET status = 'failed', result_json = ? WHERE id = ?",
                (json.dumps(failure, ensure_ascii=False), attempt_id),
            )
        else:
            result = {"status": receipt.status, "external_entry_id": receipt.external_entry_id,
                      "evidence": receipt.evidence, "external_submission": True}
            db.execute(
                "UPDATE competition_attempts SET status = ?, result_json = ? WHERE id = ?",
                (receipt.status, json.dumps(result, ensure_ascii=False), attempt_id),
            )
    if adapter_error:
        raise HTTPException(
            502,
            "Official adapter failed and the attempt was recorded. Verify the remote platform before any manual retry.",
        )
    return result


@app.get("/api/competitions/{competition_id}/history")
def competition_history(competition_id: int, actor: str = Depends(require_owner)):
    with connect() as db:
        if not db.execute("SELECT id FROM competitions WHERE id = ?", (competition_id,)).fetchone():
            raise HTTPException(404, "Competition not found.")
        rows = db.execute(
            "SELECT id, mode, status, result_json, created_at FROM competition_attempts WHERE competition_id = ? ORDER BY created_at DESC, id DESC",
            (competition_id,),
        ).fetchall()
    return [{"id": row["id"], "mode": row["mode"], "status": row["status"],
             "result": json.loads(row["result_json"]), "created_at": row["created_at"]} for row in rows]


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