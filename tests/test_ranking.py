from autoearn.ranking import rank_evaluations


def record(opportunity_id, title, currency, score, *, eligibility="eligible",
           stale=False, execution=False, flags=None):
    return {
        "opportunity_id": opportunity_id,
        "title": title,
        "evaluation": {
            "currency": currency,
            "ranking_score": score,
            "eligibility": eligibility,
            "evidence_stale": stale,
            "execution_allowed": execution,
            "risk_flags": flags or [],
        },
    }


def test_ranking_separates_currencies_and_orders_within_each_group():
    result = rank_evaluations([
        record(1, "Lower EUR", "EUR", 45),
        record(2, "Higher EUR", "eur", 82, execution=True),
        record(3, "USD item", "USD", 99),
    ])
    assert result["total"] == 3
    assert [group["currency"] for group in result["groups"]] == ["EUR", "USD"]
    eur = result["groups"][0]["items"]
    assert [item["title"] for item in eur] == ["Higher EUR", "Lower EUR"]
    assert eur[0]["rank_in_currency"] == 1
    assert result["groups"][1]["items"][0]["rank_in_currency"] == 1
    assert "not compared" in result["comparison_note"]


def test_ranking_tiers_do_not_treat_stale_or_ineligible_as_priority():
    result = rank_evaluations([
        record(1, "Fresh candidate", "EUR", 80),
        record(2, "Stale candidate", "EUR", 95, stale=True),
        record(3, "Excluded", "EUR", 99, eligibility="ineligible"),
    ])
    tiers = {item["title"]: item["priority_tier"]
             for item in result["groups"][0]["items"]}
    assert tiers["Fresh candidate"] == "priority_candidate"
    assert tiers["Stale candidate"] == "needs_review"
    assert tiers["Excluded"] == "low_priority"


def test_ranking_never_authorizes_execution():
    result = rank_evaluations([
        record(1, "Ready", "EUR", 90, execution=True),
    ])
    item = result["groups"][0]["items"][0]
    assert item["execution_allowed"] is True
    assert item["execution_authorized"] is False


def test_ai_fit_is_reported_separately_from_financial_priority():
    candidate = record(1, "AI task", "EUR", 85)
    candidate["evaluation"]["ai_task_assessment"] = {
        "suitability": "ai_draft_candidate", "score": 85,
    }
    result = rank_evaluations([candidate])
    item = result["groups"][0]["items"][0]
    assert item["priority_tier"] == "priority_candidate"
    assert item["ai_fit"] == "bounded_ai_draft_candidate"
    assert item["ai_suitability_score"] == 85
    assert item["execution_authorized"] is False
