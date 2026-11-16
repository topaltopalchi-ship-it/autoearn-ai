"""Broad, transparent taxonomy and query expansion for online earning discovery.

Categories describe opportunity types, not endorsements or verified income.
"""
from __future__ import annotations

from typing import Literal

OpportunityCategory = Literal[
    "all", "games", "surveys", "user_testing", "microtasks", "freelance",
    "cashback", "affiliate", "creator", "tutoring", "digital_products",
    "research", "bug_bounty",
]

CATEGORY_LABELS = {
    "games": "Play-to-earn and game rewards",
    "surveys": "Surveys and market research panels",
    "user_testing": "Website and app user testing",
    "microtasks": "Microtasks and data-labeling tasks",
    "freelance": "Freelance services and gigs",
    "cashback": "Cashback, loyalty and receipt rewards",
    "affiliate": "Affiliate and referral programs",
    "creator": "Content creation and creator monetization",
    "tutoring": "Tutoring, teaching and coaching",
    "digital_products": "Digital products and templates",
    "research": "Paid research studies and focus groups",
    "bug_bounty": "Responsible security research and bug bounties",
}

CATEGORY_TERMS = {
    "games": "legitimate game rewards play to earn tournaments game testing rewards",
    "surveys": "paid surveys market research panels rewards",
    "user_testing": "website app usability testing paid tester opportunities",
    "microtasks": "microtasks data annotation labeling transcription tasks",
    "freelance": "freelance remote gigs services marketplace projects",
    "cashback": "cashback receipt scanning loyalty rewards programs",
    "affiliate": "affiliate marketing publisher partner commission programs",
    "creator": "creator monetization content platform revenue programs",
    "tutoring": "online tutoring teaching coaching paid opportunities",
    "digital_products": "sell digital downloads templates stock assets creator marketplace",
    "research": "paid academic research studies focus groups participant opportunities",
    "bug_bounty": "responsible disclosure vulnerability disclosure bug bounty programs",
}

def expand_discovery_query(query: str, category: OpportunityCategory = "all") -> str:
    """Add category vocabulary to a user's query while preserving their intent."""
    cleaned = " ".join(query.split()) if isinstance(query, str) else ""
    if not cleaned or len(cleaned) > 220:
        raise ValueError("query must contain 1 to 220 characters")
    if category != "all" and category not in CATEGORY_TERMS:
        raise ValueError("unsupported opportunity category")
    if category == "all":
        terms = "online income opportunities games surveys user testing microtasks freelance cashback affiliate creator tutoring research"
    else:
        terms = CATEGORY_TERMS[category]
    return f"{cleaned} {terms}"[:300]
