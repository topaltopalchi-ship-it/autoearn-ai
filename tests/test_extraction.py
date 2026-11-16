import pytest

from autoearn.extraction import extract_opportunity_details


def test_extracts_currency_amounts_age_and_eligibility_evidence():
    result = extract_opportunity_details(
        "Earn €25 after completing the offer. Only residents of Germany are eligible. "
        "Participants must be 18+ and must read the official terms and conditions."
    )
    assert result["reward_amounts"] == [{"currency": "EUR", "amount_text": "25"}]
    assert result["minimum_age_hints"] == [18]
    assert len(result["eligibility_evidence"]) == 2
    assert result["terms_mentioned"] is True
    assert result["verified"] is False
    assert result["extraction_status"] == "needs_human_verification"


def test_extracts_currency_codes_and_deduplicates_amounts():
    result = extract_opportunity_details("Reward: USD 100. Bonus: USD 100. Fee: £5.")
    assert result["reward_amounts"] == [
        {"currency": "USD", "amount_text": "100"},
        {"currency": "GBP", "amount_text": "5"},
    ]


@pytest.mark.parametrize("text", ["", "   "])
def test_rejects_empty_text(text):
    with pytest.raises(ValueError):
        extract_opportunity_details(text)


def test_rejects_oversized_text():
    with pytest.raises(ValueError):
        extract_opportunity_details("x" * 20_001)


def test_does_not_infer_terms_or_eligibility_when_absent():
    result = extract_opportunity_details("A simple page describing a mobile game.")
    assert result["reward_amounts"] == []
    assert result["minimum_age_hints"] == []
    assert result["eligibility_evidence"] == []
    assert result["terms_mentioned"] is False
