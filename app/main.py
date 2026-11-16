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

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from autoearn.opportunities import BraveSearchProvider, discover_opportunities, normalize_url
from autoearn.mwmbl import MwmblSearchProvider
from autoearn.extraction import extract_opportunity_details
from autoearn.catalog import CATEGORY_LABELS, expand_discovery_query
from autoearn.risk import RiskSignals, assess_risk
from autoearn.ranking import RankingInput, rank_opportunity, rank_discovery_candidate
from autoearn.economics import EconomicsInput, evaluate_economics
from pydantic import BaseModel, Field, HttpUrl

from app.auth import (
    COOKIE_NAME,
    clear_login_failures,
    configured as auth_configured,
    issue_session,
    login_retry_after,
    record_login_failure,
    valid_session,
    verify_password,
)
from app import vault as credential_vault
from app.vault import VaultError

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
            estimated_reward REAL,
            reward_currency TEXT NOT NULL DEFAULT 'USD',
            estimated_hours REAL,
            eligible_countries TEXT NOT NULL DEFAULT '',
            payout_method TEXT NOT NULL DEFAULT '',
            minimum_payout REAL,
            risk_score INTEGER,
            risk_assessment_json TEXT NOT NULL DEFAULT '{}',
            economics_json TEXT NOT NULL DEFAULT '{}',
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
            promoted_opportunity_id INTEGER REFERENCES opportunities(id),
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
        opportunity_columns = {row["name"] for row in db.execute("PRAGMA table_info(opportunities)")}
        opportunity_migrations = {
            "estimated_reward": "REAL",
            "reward_currency": "TEXT NOT NULL DEFAULT 'USD'",
            "estimated_hours": "REAL",
            "eligible_countries": "TEXT NOT NULL DEFAULT ''",
            "payout_method": "TEXT NOT NULL DEFAULT ''",
            "minimum_payout": "REAL",
            "risk_score": "INTEGER",
            "risk_assessment_json": "TEXT NOT NULL DEFAULT '{}'",
            "economics_json": "TEXT NOT NULL DEFAULT '{}'",
        }
        for column, definition in opportunity_migrations.items():
            if column not in opportunity_columns:
                db.execute(f"ALTER TABLE opportunities ADD COLUMN {column} {definition}")
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
        if "promoted_opportunity_id" not in candidate_columns:
            db.execute("ALTER TABLE discovered_candidates ADD COLUMN promoted_opportunity_id INTEGER REFERENCES opportunities(id)")


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


@app.middleware("http")
async def enforce_loopback_only(request: Request, call_next):
    """Reject non-loopback traffic and unauthenticated API access."""
    peer = request.client.host if request.client else ""
    try:
        is_loopback = ipaddress.ip_address(peer).is_loopback
    except ValueError:
        is_loopback = False
    if not is_loopback:
        return JSONResponse(
            status_code=403,
            content={"detail": "This personal app only accepts loopback connections."},
        )
    if request.url.path.startswith("/api/") and request.url.path not in {"/api/auth/status", "/api/auth/login", "/api/health"}:
        if not auth_configured():
            return JSONResponse(
                status_code=503,
                content={"detail": "Owner authentication is not configured. Set AUTOEARN_MASTER_PASSWORD and AUTOEARN_AUTH_SECRET."},
            )
        if not valid_session(request.cookies.get(COOKIE_NAME)):
            return JSONResponse(status_code=401, content={"detail": "ورود مالک لازم است."})
    return await call_next(request)



class DiscoverIn(BaseModel):
    query: str = Field(min_length=1, max_length=220)
    category: Literal["all", "games", "surveys", "user_testing", "microtasks", "freelance", "cashback", "affiliate", "creator", "tutoring", "digital_products", "research", "bug_bounty"] = "all"
    limit: int = Field(default=10, ge=1, le=20)


class RiskAssessmentIn(BaseModel):
    upfront_payment: bool = False
    deposit_or_top_up: bool = False
    guaranteed_high_returns: bool = False
    referral_required_to_withdraw: bool = False
    unclear_or_missing_terms: bool = False
    missing_payout_threshold: bool = False
    crypto_only_payout: bool = False
    requests_sensitive_data_early: bool = False
    asks_to_move_off_platform: bool = False
    unrealistic_time_pressure: bool = False


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
    estimated_reward: float | None = Field(default=None, gt=0)
    reward_currency: str = Field(default="USD", min_length=3, max_length=8)
    estimated_hours: float | None = Field(default=None, gt=0)
    eligible_countries: str = Field(default="", max_length=300)
    payout_method: str = Field(default="", max_length=120)
    minimum_payout: float | None = Field(default=None, ge=0)
    risk_score: int | None = Field(default=None, ge=0, le=100)


class EconomicsEvaluateIn(BaseModel):
    gross_reward: float = Field(ge=0, allow_inf_nan=False)
    estimated_hours: float = Field(gt=0, allow_inf_nan=False)
    estimated_cost: float = Field(default=0, ge=0, allow_inf_nan=False)
    fee_percent: float = Field(default=0, ge=0, le=100, allow_inf_nan=False)
    flat_fee: float = Field(default=0, ge=0, allow_inf_nan=False)
    currency: str = Field(default="EUR", min_length=3, max_length=3)
    cost_currency: str | None = Field(default=None, min_length=3, max_length=3)
    target_hourly_rate: float | None = Field(default=None, ge=0, allow_inf_nan=False)


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
    return HTMLResponse((STATIC_DIR / "index.html").read_text(encoding="utf-8"))


class LoginIn(BaseModel):
    password: str = Field(min_length=1, max_length=200)


class VaultCredentialIn(BaseModel):
    label: str = Field(min_length=1, max_length=80)
    provider: str = Field(min_length=1, max_length=80)
    credential_type: Literal["api_key", "access_token", "signing_key", "account_secret"]
    secret: str = Field(min_length=1, max_length=8192)
    passphrase: str = Field(min_length=14, max_length=1024)


class VaultCredentialUpdateIn(BaseModel):
    secret: str = Field(min_length=1, max_length=8192)
    passphrase: str = Field(min_length=14, max_length=1024)


class VaultCredentialDeleteIn(BaseModel):
    passphrase: str = Field(min_length=14, max_length=1024)


class VaultConnectionCheckIn(BaseModel):
    passphrase: str = Field(min_length=14, max_length=1024)


@app.get("/api/auth/status")
def auth_status(request: Request):
    return {"configured": auth_configured(), "authenticated": valid_session(request.cookies.get(COOKIE_NAME))}


@app.post("/api/auth/login")
def auth_login(data: LoginIn, request: Request, response: Response):
    if not auth_configured():
        raise HTTPException(503, "Owner authentication is not configured.")
    client_key = request.client.host if request.client else "unknown"
    retry_after = login_retry_after(client_key)
    if retry_after:
        raise HTTPException(
            429,
            "تعداد تلاش‌های ورود بیش از حد مجاز است. کمی بعد دوباره تلاش کنید.",
            headers={"Retry-After": str(retry_after)},
        )
    if not verify_password(data.password):
        record_login_failure(client_key)
        raise HTTPException(401, "رمز ورود نادرست است.")
    clear_login_failures(client_key)
    response.set_cookie(
        COOKIE_NAME,
        issue_session(),
        max_age=12 * 60 * 60,
        httponly=True,
        samesite="strict",
        secure=False,
        path="/",
    )
    return {"authenticated": True}


@app.post("/api/auth/logout")
def auth_logout(response: Response):
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"authenticated": False}


@app.get("/api/vault/credentials")
def vault_list_credentials():
    """Return credential metadata only; secret values are never serialized."""
    return credential_vault.list_credentials()


@app.post("/api/vault/credentials", status_code=201)
def vault_add_credential(data: VaultCredentialIn):
    try:
        return credential_vault.add_credential(
            label=data.label, provider=data.provider,
            credential_type=data.credential_type, secret=data.secret,
            passphrase=data.passphrase,
        )
    except VaultError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.put("/api/vault/credentials/{credential_id}")
def vault_update_credential(credential_id: int, data: VaultCredentialUpdateIn):
    try:
        return credential_vault.update_credential(
            credential_id, secret=data.secret, passphrase=data.passphrase,
        )
    except KeyError as exc:
        raise HTTPException(404, "کلید موردنظر پیدا نشد.") from exc
    except VaultError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.delete("/api/vault/credentials/{credential_id}")
def vault_delete_credential(credential_id: int, data: VaultCredentialDeleteIn):
    try:
        credential_vault.delete_credential(credential_id, data.passphrase)
        return {"deleted": True}
    except KeyError as exc:
        raise HTTPException(404, "کلید موردنظر پیدا نشد.") from exc
    except VaultError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/vault/credentials/{credential_id}/test-connection")
def vault_test_connection(credential_id: int, data: VaultConnectionCheckIn):
    """Test a saved provider key only after an explicit owner request."""
    try:
        metadata = next(
            (item for item in credential_vault.list_credentials() if item["id"] == credential_id),
            None,
        )
        if metadata is None:
            raise HTTPException(404, "کلید موردنظر پیدا نشد.")
        if metadata["provider"].strip().lower() != "openai" or metadata["credential_type"] != "api_key":
            raise HTTPException(422, "آزمایش اتصال فعلاً فقط برای کلید API سرویس OpenAI فعال است.")
        secret = credential_vault.get_secret(credential_id, data.passphrase)
        from app.provider_checks import check_openai_api_key
        return check_openai_api_key(secret)
    except KeyError as exc:
        raise HTTPException(404, "کلید موردنظر پیدا نشد.") from exc
    except VaultError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get("/api/discovery-categories")
def discovery_categories():
    return [{"id": key, "label": label} for key, label in CATEGORY_LABELS.items()]


@app.post("/api/opportunities/evaluate")
def evaluate_opportunity_economics(data: EconomicsEvaluateIn):
    """Calculate estimated net return from owner-entered figures; no API calls."""
    try:
        return evaluate_economics(EconomicsInput(
            gross_reward=data.gross_reward,
            estimated_hours=data.estimated_hours,
            estimated_cost=data.estimated_cost,
            fee_percent=data.fee_percent,
            flat_fee=data.flat_fee,
            currency=data.currency,
            cost_currency=data.cost_currency or data.currency,
            target_hourly_rate=data.target_hourly_rate,
        ))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.post("/api/risk-assessments")
def risk_assessment(data: RiskAssessmentIn):
    return assess_risk(RiskSignals(**data.model_dump()))


@app.post("/api/opportunities/{opportunity_id}/risk-assessment")
def persist_opportunity_risk_assessment(opportunity_id: int, data: RiskAssessmentIn):
    """Assess and persist transparent risk signals on the selected opportunity."""
    assessment = assess_risk(RiskSignals(**data.model_dump()))
    with connect() as db:
        row = db.execute("SELECT id FROM opportunities WHERE id = ?", (opportunity_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Opportunity not found")
        db.execute(
            "UPDATE opportunities SET risk_score = ?, risk_assessment_json = ? WHERE id = ?",
            (assessment["risk_score"], json.dumps(assessment), opportunity_id),
        )
        saved = db.execute("SELECT * FROM opportunities WHERE id = ?", (opportunity_id,)).fetchone()
    result = row_dict(saved)
    result["risk_assessment"] = json.loads(result.pop("risk_assessment_json") or "{}")
    result["economics"] = json.loads(result.pop("economics_json") or "{}")
    return {"opportunity": result, "assessment": assessment}


@app.post("/api/opportunities/{opportunity_id}/evaluate")
def persist_opportunity_economics(opportunity_id: int, data: EconomicsEvaluateIn):
    """Calculate and persist an owner-entered estimate on its opportunity record."""
    try:
        assessment = evaluate_economics(EconomicsInput(
            gross_reward=data.gross_reward,
            estimated_hours=data.estimated_hours,
            estimated_cost=data.estimated_cost,
            fee_percent=data.fee_percent,
            flat_fee=data.flat_fee,
            currency=data.currency,
            cost_currency=data.cost_currency or data.currency,
            target_hourly_rate=data.target_hourly_rate,
        ))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    with connect() as db:
        row = db.execute("SELECT id FROM opportunities WHERE id = ?", (opportunity_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Opportunity not found")
        db.execute(
            "UPDATE opportunities SET economics_json = ?, estimated_reward = ?, reward_currency = ?, estimated_hours = ? WHERE id = ?",
            (json.dumps(assessment), data.gross_reward, assessment["currency"], data.estimated_hours, opportunity_id),
        )
        saved = db.execute("SELECT * FROM opportunities WHERE id = ?", (opportunity_id,)).fetchone()
    result = row_dict(saved)
    result["risk_assessment"] = json.loads(result.pop("risk_assessment_json") or "{}")
    result["economics"] = json.loads(result.pop("economics_json") or "{}")
    return {"opportunity": result, "assessment": assessment}


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "AutoEarn AI", "version": app.version}


@app.post("/api/discover")
def discover(data: DiscoverIn):
    brave_key = os.getenv("BRAVE_SEARCH_API_KEY", "").strip()
    mwmbl_key = os.getenv("MWMBL_API_KEY", "").strip()
    try:
        # Prefer Brave when explicitly configured; otherwise use the Mwmbl
        # adapter. Availability, authentication requirements, and usage limits
        # must be verified against the provider's current documentation.
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
                "review_status": row["review_status"],
                "promoted_opportunity_id": row["promoted_opportunity_id"],
                "review_priority": rank_discovery_candidate(
                    row["confidence"], json.loads(row["extraction_json"]), row["review_status"]
                ),
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
            "promoted_opportunity_id": row["promoted_opportunity_id"],
            "verified": False,
        }
        for row in rows
    ]


@app.get("/api/discoveries/ranked")
def ranked_discoveries(
    review_status: Literal["pending", "accepted", "rejected"] | None = None,
    limit: int = Query(default=50, ge=1, le=200),
):
    """Return discovery leads ordered by evidence-based human-review priority."""
    sql = "SELECT * FROM discovered_candidates"
    params = []
    if review_status:
        sql += " WHERE review_status = ?"
        params.append(review_status)
    with connect() as db:
        rows = db.execute(sql, params).fetchall()
    ranked = []
    for row in rows:
        extraction = json.loads(row["extraction_json"])
        priority = rank_discovery_candidate(row["confidence"], extraction, row["review_status"])
        ranked.append({
            "id": row["id"],
            "title": row["title"],
            "url": row["canonical_url"],
            "domain": row["domain"],
            "category": row["category"],
            "confidence": row["confidence"],
            "review_status": row["review_status"],
            "extraction": extraction,
            "review_priority": priority,
            "verified": False,
        })
    ranked.sort(
        key=lambda item: (item["review_priority"]["review_priority_score"], item["confidence"]),
        reverse=True,
    )
    return ranked[:limit]


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
    with connect() as db:
        row = db.execute(
            "SELECT confidence, review_status FROM discovered_candidates WHERE id = ?", (candidate_id,)
        ).fetchone()
    return {
        "candidate_id": candidate_id,
        "extraction": extracted,
        "review_priority": rank_discovery_candidate(row["confidence"], extracted, row["review_status"]),
        "verified": False,
    }


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


@app.post("/api/discoveries/{candidate_id}/promote")
def promote_discovery(candidate_id: int):
    """Create a tracked opportunity only after explicit human acceptance."""
    with connect() as db:
        candidate = db.execute(
            "SELECT * FROM discovered_candidates WHERE id = ?", (candidate_id,)
        ).fetchone()
        if not candidate:
            raise HTTPException(404, "Discovered candidate not found")
        if candidate["review_status"] != "accepted":
            raise HTTPException(409, "Only candidates explicitly accepted by the owner can be added.")
        if candidate["promoted_opportunity_id"] is not None:
            existing = db.execute(
                "SELECT * FROM opportunities WHERE id = ?",
                (candidate["promoted_opportunity_id"],),
            ).fetchone()
            if existing:
                return {"opportunity": row_dict(existing), "already_promoted": True}

        existing = db.execute(
            "SELECT * FROM opportunities WHERE url = ?", (candidate["canonical_url"],)
        ).fetchone()
        if existing:
            db.execute(
                "UPDATE discovered_candidates SET promoted_opportunity_id = ? WHERE id = ?",
                (existing["id"], candidate_id),
            )
            return {"opportunity": row_dict(existing), "already_promoted": True, "already_exists": True}

        extraction = json.loads(candidate["extraction_json"] or "{}")
        amount_hints = extraction.get("reward_amounts") or []
        reward_parts = [
            f'{item.get("currency", "")} {item.get("amount_text", "")}'.strip()
            for item in amount_hints
            if isinstance(item, dict) and item.get("amount_text")
        ]
        reward_description = (
            "مبالغ ذکرشده در متن ارسالی (تأییدنشده): " + "، ".join(reward_parts[:5])
            if reward_parts else ""
        )
        eligibility = "؛ ".join(extraction.get("eligibility_evidence") or [])[:1000]
        notes_parts = [
            "افزوده‌شده از صندوق کشف؛ هنوز تأیید اعتبار یا پرداخت نیست.",
            (candidate["snippet"] or "")[:400],
            (candidate["review_note"] or "")[:500],
            extraction.get("disclaimer", ""),
        ]
        notes = " ".join(part for part in notes_parts if part).strip()[:1000]
        title = (candidate["title"] or candidate["domain"] or "Discovered opportunity")[:160]
        platform = (candidate["domain"] or urlparse(candidate["canonical_url"]).hostname or "Unknown")[:100]
        category = (candidate["category"] or "other")[:40]
        score = 20 + (15 if reward_description else 0) + (20 if eligibility else 0)
        cursor = db.execute(
            """
            INSERT INTO opportunities
            (title, platform, url, category, reward_description, eligibility, notes, score, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (title, platform, candidate["canonical_url"], category,
             reward_description, eligibility, notes, score, now()),
        )
        opportunity = db.execute(
            "SELECT * FROM opportunities WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
        db.execute(
            "UPDATE discovered_candidates SET promoted_opportunity_id = ? WHERE id = ?",
            (cursor.lastrowid, candidate_id),
        )
        return {"opportunity": row_dict(opportunity), "already_promoted": False, "already_exists": False}


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


@app.get("/api/opportunities/ranked")
def ranked_opportunities(country: str | None = Query(default=None, min_length=2, max_length=2)):
    """List tracked opportunities by explainable fit score for an optional ISO country code."""
    with connect() as db:
        rows = db.execute("SELECT * FROM opportunities ORDER BY created_at DESC").fetchall()
    ranked = []
    for row in rows:
        item = row_dict(row)
        result = rank_opportunity(RankingInput(
            estimated_reward=item.get("estimated_reward"),
            estimated_hours=item.get("estimated_hours"),
            eligible_countries=item.get("eligible_countries", ""),
            payout_method=item.get("payout_method", ""),
            minimum_payout=item.get("minimum_payout"),
            risk_score=item.get("risk_score"),
        ), country=country)
        ranked.append({**item, "ranking": result})
    return sorted(ranked, key=lambda item: (item["ranking"]["ranking_score"], item["ranking"]["data_coverage"]), reverse=True)


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
            (title, platform, url, category, reward_description, eligibility, terms_url, notes, score,
             estimated_reward, reward_currency, estimated_hours, eligible_countries, payout_method,
             minimum_payout, risk_score, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (payload["title"], payload["platform"], payload["url"], payload["category"],
              payload["reward_description"], payload["eligibility"], payload["terms_url"],
              payload["notes"], score, payload["estimated_reward"], payload["reward_currency"].upper(),
              payload["estimated_hours"], payload["eligible_countries"], payload["payout_method"],
              payload["minimum_payout"], payload["risk_score"], now()))
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
        paid_rows = db.execute(
            "SELECT UPPER(currency) AS currency, ROUND(SUM(amount), 2) AS amount "
            "FROM rewards WHERE status = 'paid' GROUP BY UPPER(currency) ORDER BY UPPER(currency)"
        ).fetchall()
        pending_rows = db.execute(
            "SELECT UPPER(currency) AS currency, ROUND(SUM(amount), 2) AS amount "
            "FROM rewards WHERE status = 'pending' GROUP BY UPPER(currency) ORDER BY UPPER(currency)"
        ).fetchall()
        paid_by_currency = [row_dict(row) for row in paid_rows]
        pending_by_currency = [row_dict(row) for row in pending_rows]
        # Keep scalar fields only when a single currency exists; never add unlike currencies.
        paid_total = paid_by_currency[0]["amount"] if len(paid_by_currency) == 1 else (0 if not paid_by_currency else None)
        pending_total = pending_by_currency[0]["amount"] if len(pending_by_currency) == 1 else (0 if not pending_by_currency else None)
        return {
            "opportunities": opportunities,
            "tasks": tasks,
            "awaiting_approval": awaiting,
            "paid_total": paid_total,
            "pending_total": pending_total,
            "paid_currency": paid_by_currency[0]["currency"] if len(paid_by_currency) == 1 else None,
            "pending_currency": pending_by_currency[0]["currency"] if len(pending_by_currency) == 1 else None,
            "paid_by_currency": paid_by_currency,
            "pending_by_currency": pending_by_currency,
        }
