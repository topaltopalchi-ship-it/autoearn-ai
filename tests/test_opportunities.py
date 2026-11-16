import pytest
import unittest

from autoearn.opportunities import Opportunity, normalize_url, score_opportunity


class NormalizeUrlTests(unittest.TestCase):
    def test_removes_tracking_and_fragment(self):
        self.assertEqual(
            normalize_url("HTTPS://Example.com/path/?utm_source=x&b=2#section"),
            "https://example.com/path?b=2",
        )

    def test_rejects_unsafe_schemes_and_credentials(self):
        for url in ("javascript:alert(1)", "file:///etc/passwd", "https://user:pass@example.com"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                normalize_url(url)


class OpportunityTests(unittest.TestCase):
    def test_score_is_weighted_and_explained(self):
        item = Opportunity("Demo", "https://example.com", 100, 100, 100, 100, 100)
        result = score_opportunity(item)
        self.assertEqual(result["score"], 100)
        self.assertEqual(result["risk"], "low")
        self.assertEqual(len(result["reasons"]), 5)

    def test_rejects_out_of_range_values(self):
        with self.assertRaises(ValueError):
            Opportunity("Demo", "https://example.com", source_trust=101)

    def test_low_score_is_high_risk(self):
        item = Opportunity("Demo", "https://example.com")
        self.assertEqual(score_opportunity(item)["risk"], "high")


if __name__ == "__main__":
    unittest.main()


class FakeSearchProvider:
    def __init__(self, results):
        self.results = results
        self.calls = []

    def search(self, query, limit=10):
        self.calls.append((query, limit))
        return self.results


def test_discovery_canonicalizes_and_deduplicates_results():
    from autoearn.opportunities import discover_opportunities

    provider = FakeSearchProvider([
        {"title": "Rewards and eligibility", "url": "https://EXAMPLE.com/rewards/?utm_source=x",
         "snippet": "See terms and conditions. Eligible regions.", "provider": "fixture"},
        {"title": "Duplicate", "url": "https://example.com/rewards/"},
        {"title": "Private target", "url": "http://127.0.0.1/admin"},
        {"title": "Bad scheme", "url": "javascript:alert(1)"},
    ])
    found = discover_opportunities("  game   rewards ", provider, limit=5)

    assert len(found) == 1
    assert found[0].url == "https://example.com/rewards"
    assert found[0].domain == "example.com"
    assert found[0].review_required is True
    assert found[0].confidence > 15
    assert "reward_language_found" in found[0].signals
    assert provider.calls == [("game rewards", 5)]


def test_discovery_limits_and_validates_query():
    from autoearn.opportunities import discover_opportunities

    provider = FakeSearchProvider([])
    for query, limit in (("", 5), ("valid", 0), ("valid", 51), ("valid", True)):
        with pytest.raises(ValueError):
            discover_opportunities(query, provider, limit=limit)


def test_discovery_keeps_results_unverified_and_handles_empty_batch():
    from autoearn.opportunities import discover_opportunities

    provider = FakeSearchProvider([
        {"title": "A plain page", "url": "https://example.org/about", "snippet": "About us"}
    ])
    item = discover_opportunities("research", provider)[0]
    assert item.confidence == 30
    assert item.review_required is True
    assert item.signals == ("https_transport",)
