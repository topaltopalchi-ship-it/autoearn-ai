"""Focused opportunity tracks for the first AutoEarn AI discovery priorities.

Tracks refine the broad adapter categories without implying platform eligibility
or permission to automate. Every candidate still requires country, payout, terms,
and source verification before participation.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ParentCategory = Literal[
    "games_competitions",
    "surveys_microtasks",
    "freelancing_services",
    "ai_content_products",
    "other",
]
ExecutionGuidance = Literal["human_required", "assist_if_permitted", "official_api_only"]


@dataclass(frozen=True)
class OpportunityTrack:
    key: str
    label: str
    parent_category: ParentCategory
    execution_guidance: ExecutionGuidance
    priority: int
    description: str


TRACKS: tuple[OpportunityTrack, ...] = (
    OpportunityTrack(
        "game_playtesting", "تست بازی", "games_competitions",
        "human_required", 1,
        "بازخورد واقعی بازیکن؛ بازی و گزارش تجربه باید توسط خود کاربر انجام شود.",
    ),
    OpportunityTrack(
        "puzzle_solving", "حل پازل", "games_competitions",
        "assist_if_permitted", 2,
        "پازل و معمای مهارتی؛ کمک هوش مصنوعی فقط در صورت اجازه صریح قوانین.",
    ),
    OpportunityTrack(
        "iq_reasoning", "آزمون هوش و استدلال", "games_competitions",
        "assist_if_permitted", 3,
        "آزمون‌های منطق و استدلال؛ پاسخ‌گویی به‌جای شرکت‌کننده ممنوع مگر صریحاً مجاز باشد.",
    ),
    OpportunityTrack(
        "skill_competitions", "مسابقات مهارتی", "games_competitions",
        "official_api_only", 4,
        "مسابقات رسمی و مهارت‌محور؛ بدون شرط‌بندی، تقلب یا دست‌کاری امتیاز.",
    ),
    OpportunityTrack(
        "bug_testing", "گزارش باگ", "freelancing_services",
        "assist_if_permitted", 5,
        "کشف و مستندسازی ایراد؛ گزارش باید بازتولیدپذیر و توسط کاربر بازبینی شود.",
    ),
    OpportunityTrack(
        "software_qa", "تست نرم‌افزار", "freelancing_services",
        "human_required", 6,
        "اجرای سناریوهای واقعی و ثبت نتیجه؛ تست انسانی را نباید جعل یا شبیه‌سازی کرد.",
    ),
    OpportunityTrack(
        "ai_data_tasks", "وظایف داده و هوش مصنوعی", "surveys_microtasks",
        "assist_if_permitted", 7,
        "برچسب‌گذاری و ارزیابی داده فقط مطابق دستورالعمل و قوانین هر کارفرما.",
    ),
    OpportunityTrack(
        "microtasks", "مأموریت‌های خرد", "surveys_microtasks",
        "assist_if_permitted", 8,
        "کارهای کوتاه با پاداش روشن؛ بدون پاسخ جعلی، کلیک ساختگی یا دور زدن کنترل‌ها.",
    ),
    OpportunityTrack(
        "freelance_projects", "پروژه‌های فریلنسری", "freelancing_services",
        "assist_if_permitted", 9,
        "پروژه‌های خدماتی؛ تحویل، قرارداد و ارسال نهایی با تأیید کاربر.",
    ),
)

_TRACK_BY_KEY = {track.key: track for track in TRACKS}


def list_tracks() -> list[OpportunityTrack]:
    """Return the stable, priority-ordered discovery tracks."""
    return list(TRACKS)


def get_track(key: str) -> OpportunityTrack | None:
    """Return one known track; unknown values are not silently accepted."""
    return _TRACK_BY_KEY.get(key)


def tracks_for_category(category: str) -> tuple[OpportunityTrack, ...]:
    """Return compatible tracks; multiple matches must remain ambiguous."""
    return tuple(track for track in TRACKS if track.parent_category == category)


_TRACK_KEYWORDS = {
    "game_playtesting": ("playtest", "game testing", "test a game", "تست بازی", "بازی آزمایی"),
    "puzzle_solving": ("puzzle", "logic puzzle", "brain teaser", "حل پازل", "معما", "چیستان"),
    "iq_reasoning": ("iq test", "reasoning test", "logic test", "آزمون هوش", "تست هوش", "استدلال"),
    "skill_competitions": ("skill contest", "skill competition", "tournament", "مسابقه مهارتی", "مسابقات مهارتی"),
    "bug_testing": ("bug bounty", "bug report", "report a bug", "گزارش باگ", "گزارش خطا", "اشکال نرم افزار"),
    "software_qa": ("software testing", "qa testing", "test software", "تست نرم افزار", "آزمون نرم افزار"),
    "ai_data_tasks": ("data annotation", "ai training", "label data", "برچسب گذاری داده", "برچسب گذاری اطلاعات", "وظایف داده", "آموزش هوش مصنوعی"),
    "microtasks": ("microtask", "small task", "paid survey", "مأموریت خرد", "وظیفه خرد", "کار کوچک", "نظرسنجی پولی"),
    "freelance_projects": ("freelance project", "client project", "contract work", "پروژه فریلنسری", "پروژه آزادکاری", "پروژه دورکاری"),
}


def _normalize_track_text(value: str) -> str:
    """Normalize common Persian/Arabic keyboard variants before matching."""
    return (
        value.replace("\u064a", "\u06cc")
        .replace("\u0643", "\u06a9")
        .replace("\u0640", "")
        .replace("\u200c", " ")
        .casefold()
    )


def infer_track_from_text(title: str, summary: str, category: str) -> str:
    """Infer only a unique track; ambiguous candidates remain for manual review."""
    text = _normalize_track_text(f"{title} {summary}")
    matches = [
        track.key for track in tracks_for_category(category)
        if any(_normalize_track_text(term) in text for term in _TRACK_KEYWORDS.get(track.key, ()))
    ]
    return matches[0] if len(matches) == 1 else ""


def track_matches_category(key: str, category: str) -> bool:
    """Check that a track belongs to the adapter's declared parent category."""
    track = get_track(key)
    return track is not None and track.parent_category == category
