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

    def test_rejects_invalid_title_types(self):
        for title in (None, 7, True):
            with self.subTest(title=title), self.assertRaises(ValueError):
                Opportunity(title, "https://example.com")

    def test_low_score_is_high_risk(self):
        item = Opportunity("Demo", "https://example.com")
        self.assertEqual(score_opportunity(item)["risk"], "high")


if __name__ == "__main__":
    unittest.main()
