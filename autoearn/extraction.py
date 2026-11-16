"""Conservative extraction of reward and eligibility hints from supplied page text.

This module does not fetch URLs or assert that a reward is real. Text must be
provided by a user or a separately approved, safe page-fetching component.
"""
from __future__ import annotations

import re

_AMOUNT_RE = re.compile(
    r"(?<![\w])(?P<currency>USD|EUR|GBP|CAD|AUD|\$|€|£)\s*"
    r"(?P<amount>\d{1,3}(?:[,. ]\d{3})*(?:[.,]\d{1,2})?|\d+(?:[.,]\d{1,2})?)",
    re.IGNORECASE,
)
_AGE_PATTERNS = (
    re.compile(r"\b(?:18|19|21)\s*\+(?!\d)", re.IGNORECASE),
    re.compile(r"\b(?:at least|minimum age(?: of)?)\s*(18|19|21)\s*(?:years? old)?\b", re.IGNORECASE),
)
_TERMS_RE = re.compile(r"\b(terms(?: and conditions)?|conditions|official rules|eligibility rules)\b", re.I)
_ELIGIBILITY_RE = re.compile(
    r"\b(eligible|eligibility|residents? of|available in|only in|restricted to|must be located in|age requirement)\b",
    re.I,
)


def extract_opportunity_details(page_text: str) -> dict:
    """Extract review hints; never treats text matches as verified facts."""
    if not isinstance(page_text, str) or not page_text.strip():
        raise ValueError("page_text must not be empty")
    if len(page_text) > 20_000:
        raise ValueError("page_text must be at most 20000 characters")

    text = " ".join(page_text.split())
    amounts = []
    seen_amounts = set()
    currency_names = {"$": "USD", "€": "EUR", "£": "GBP"}
    for match in _AMOUNT_RE.finditer(text):
        currency = match.group("currency").upper()
        currency = currency_names.get(currency, currency)
        amount = match.group("amount").strip()
        key = (currency, amount)
        if key not in seen_amounts:
            seen_amounts.add(key)
            amounts.append({"currency": currency, "amount_text": amount})

    age_requirements = sorted({
        int(match.group(1) or match.group(0).replace("+", ""))
        for pattern in _AGE_PATTERNS
        for match in pattern.finditer(text)
    })

    evidence = []
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        if _ELIGIBILITY_RE.search(sentence):
            clipped = sentence[:400]
            if clipped not in evidence:
                evidence.append(clipped)
        if len(evidence) >= 10:
            break

    return {
        "reward_amounts": amounts[:20],
        "minimum_age_hints": age_requirements,
        "eligibility_evidence": evidence,
        "terms_mentioned": bool(_TERMS_RE.search(text)),
        "extraction_status": "needs_human_verification",
        "verified": False,
        "disclaimer": (
            "Extracted from supplied text only. Amounts, eligibility, geography, "
            "and terms are unverified and may be incomplete or outdated."
        ),
    }
