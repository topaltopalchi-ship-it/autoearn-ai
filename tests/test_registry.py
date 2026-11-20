import unittest

from autoearn.discovery import SourceCandidate
from autoearn.registry import SourceRegistry


class SourceRegistryTests(unittest.TestCase):
    def test_adds_candidate_and_auto_approves_it_for_manual_access(self):
        registry = SourceRegistry()
        item = SourceCandidate("Game A", "https://example.com/rewards")
        stored, created = registry.add(item)
        self.assertTrue(created)
        self.assertEqual(stored.to_record()["status"], "eligible")
        self.assertEqual(len(registry), 1)

    def test_duplicate_canonical_url_is_not_added_twice(self):
        registry = SourceRegistry()
        first = SourceCandidate("Original", "https://example.com/rewards/?utm_source=x")
        second = SourceCandidate("Duplicate", "HTTPS://EXAMPLE.COM/rewards")
        registry.add(first)
        stored, created = registry.add(second)
        self.assertFalse(created)
        self.assertEqual(stored.name, "Original")
        self.assertEqual(len(registry), 1)

    def test_get_uses_normalized_url(self):
        registry = SourceRegistry()
        item = SourceCandidate("Game A", "https://example.com/rewards")
        registry.add(item)
        self.assertEqual(registry.get("https://EXAMPLE.com/rewards/?gclid=abc"), item)

    def test_list_filters_status_and_rejects_invalid_filter(self):
        registry = SourceRegistry()
        registry.add(SourceCandidate("Game A", "https://a.example.com"))
        self.assertEqual(len(registry.list("eligible")), 1)
        with self.assertRaises(ValueError):
            registry.list("pending")


if __name__ == "__main__":
    unittest.main()
