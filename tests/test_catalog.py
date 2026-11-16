import pytest

from autoearn.catalog import CATEGORY_LABELS, expand_discovery_query


def test_catalog_covers_both_requested_groups_and_broader_income_types():
    assert {"games", "surveys", "user_testing", "microtasks", "freelance",
            "cashback", "affiliate", "creator", "tutoring", "digital_products",
            "research", "bug_bounty"} <= set(CATEGORY_LABELS)


@pytest.mark.parametrize("category", list(CATEGORY_LABELS))
def test_expansion_preserves_user_query_and_adds_category_terms(category):
    expanded = expand_discovery_query("remote earning in Europe", category)
    assert expanded.startswith("remote earning in Europe ")
    assert len(expanded) <= 300


def test_all_category_is_broad():
    expanded = expand_discovery_query("legitimate opportunities", "all")
    assert "surveys" in expanded
    assert "freelance" in expanded


def test_invalid_query_or_category_is_rejected():
    with pytest.raises(ValueError):
        expand_discovery_query(" ")
    with pytest.raises(ValueError):
        expand_discovery_query("valid", "unknown")
