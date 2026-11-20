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


    def test_rejects_non_https_private_and_nonstandard_port_source_urls(self):
        for url in (
            "http://example.com",
            "https://localhost",
            "https://service.internal",
            "https://127.0.0.1",
            "https://192.168.1.20",
            "https://example.com:8443",
            "https://user:pass@example.com",
        ):
            with self.subTest(url=url), self.assertRaises(ValueError):
                SourceCandidate("Unsafe", url)

    def test_rejects_unsafe_terms_url_even_when_source_is_valid(self):
        for terms_url in ("http://example.com/terms", "https://127.0.0.1/terms", "https://example.com:9443/terms"):
            with self.subTest(terms_url=terms_url), self.assertRaises(ValueError):
                SourceCandidate("Example", "https://example.com", terms_url=terms_url)

if __name__ == "__main__":
    unittest.main()
