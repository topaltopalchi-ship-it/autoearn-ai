"""Conservative policy gate for opportunity automation.

This module classifies eligibility only; it never interacts with third-party sites.
"""
from typing import Literal

AutomationPolicy = Literal["allowed", "prohibited", "unknown"]
OpportunityCategory = Literal["ordinary", "giveaway_free", "skill_contest", "paid_lottery", "betting"]


def derive_automation_eligibility(
    automation_policy: AutomationPolicy,
    captcha_required: bool | None,
    opportunity_category: OpportunityCategory,
) -> Literal["auto", "manual_only", "excluded"]:
    """Fail closed when policy/CAPTCHA status is unknown or automation is disallowed."""
    if automation_policy == "prohibited":
        return "excluded"
    if opportunity_category in {"paid_lottery", "betting"}:
        return "manual_only"
    if captcha_required is True:
        return "manual_only"
    if automation_policy != "allowed" or captcha_required is not False:
        return "manual_only"
    return "auto"
