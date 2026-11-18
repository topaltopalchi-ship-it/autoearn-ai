import unittest

from autoearn.discovery import SourceCandidate


class SourceCandidateTests(unittest.TestCase):
    def test_normalizes_source_and_terms_urls(self):
        candidate = SourceCandidate(
            "Example Rewards",
            "HTTPS://Example.com/join/?utm_source=news#top",
            terms_url="https://example.com/terms?gclid=tracking",
            country_notes="Check regional eligibility",
            payment_notes="Verify payout threshold",
        )
        record = candidate.to_record()
        self.assertEqual(record["url"], "https://example.com/join")
        self.assertEqual(record["terms_url"], "https://example.com/terms")
        self.assertEqual(record["status"], "pending")

    def test_duplicate_key_uses_canonical_url(self):
        first = SourceCandidate("A", "https://example.com/path/?utm_campaign=x")
        second = SourceCandidate("B", "HTTPS://EXAMPLE.COM/path")
        self.assertEqual(first.duplicate_key, second.duplicate_key)

    def test_rejects_unsafe_source_and_terms_urls(self):
        with self.assertRaises(ValueError):
            SourceCandidate("Bad", "javascript:alert(1)")
        with self.assertRaises(ValueError):
            SourceCandidate("Bad", "https://example.com", terms_url="file:///etc/passwd")

    def test_rejects_unknown_review_status(self):
        with self.assertRaises(ValueError):
            SourceCandidate("Example", "https://example.com", status="auto_approved")

    def test_rejects_empty_name(self):
        with self.assertRaises(ValueError):
            SourceCandidate(" ", "https://example.com")

    def test_rejects_invalid_field_types(self):
        invalid = [
            {"url": 123},
            {"terms_url": True},
            {"terms_url": ""},
            {"country_notes": None},
            {"payment_notes": 1},
            {"status": []},
            {"track_review_status": {}},
            {"track_key": None},
            {"discovered_at": 123},
        ]
        for changes in invalid:
            with self.subTest(changes=changes):
                values = {"name": "Example", "url": "https://example.com"}
                values.update(changes)
                with self.assertRaises(ValueError):
                    SourceCandidate(**values)


if __name__ == "__main__":
    unittest.main()
