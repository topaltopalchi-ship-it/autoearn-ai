from autoearn.ranking import RankingInput, rank_opportunity


def test_complete_metadata_has_full_coverage_and_country_match():
    result = rank_opportunity(
        RankingInput(
            estimated_reward=25,
            estimated_hours=2,
            eligible_countries="DE,AT",
            payout_method="Bank transfer",
            minimum_payout=10,
            risk_score=10,
        ),
        country="DE",
    )
    assert result["data_coverage"] == 100
    assert result["ranking_score"] > 70
    assert result["warnings"] == []


def test_country_mismatch_reduces_fit():
    match = rank_opportunity(RankingInput(eligible_countries="DE"), country="DE")
    mismatch = rank_opportunity(RankingInput(eligible_countries="DE"), country="US")
    assert match["components"][2]["score"] == 100
    assert mismatch["components"][2]["score"] == 0


def test_missing_information_is_unknown_and_warned():
    result = rank_opportunity(RankingInput())
    assert result["data_coverage"] == 0
    assert len(result["warnings"]) == 6
    assert "تضمین" in result["disclaimer"]


def test_risk_score_reduces_ranking():
    safe = rank_opportunity(RankingInput(risk_score=5))
    risky = rank_opportunity(RankingInput(risk_score=90))
    assert safe["ranking_score"] > risky["ranking_score"]
