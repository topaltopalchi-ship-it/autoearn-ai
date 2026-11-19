import unittest

from autoearn.opportunities import (\n    EligibilityReview, Opportunity, evaluate_eligibility, normalize_url, score_opportunity,\n)


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
        item = Opportunity("Demo", "https://example.com", 100, 100, 100, 100)
        result = score_opportunity(item)
        self.assertEqual(result["score"], 100)
        self.assertEqual(result["risk"], "low")
        self.assertEqual(len(result["reasons"]), 4)

    def test_scoring_does_not_use_region_or_country_fit(self):
        item = Opportunity(
            "Demo",
            "https://example.com",
            reward_clarity=100,
            terms_clarity=100,
            source_trust=100,
            effort_fit=0,
        )
        result = score_opportunity(item)
        self.assertEqual(result["score"], 90)
        self.assertFalse(any("region" in reason.lower() or "country" in reason.lower()
                             for reason in result["reasons"]))

    def test_rejects_out_of_range_values(self):
        with self.assertRaises(ValueError):
            Opportunity("Demo", "https://example.com", source_trust=101)

    def test_low_score_is_high_risk(self):
        item = Opportunity("Demo", "https://example.com")
        self.assertEqual(score_opportunity(item)["risk"], "high")


class EligibilityReviewTests(unittest.TestCase):
    def test_fails_closed_when_any_confirmation_is_missing(self):
        review = EligibilityReview(
            official_terms_reviewed=True,
            country_eligible=True,
            supported_cash_payout=True,
            no_deposit_or_purchase=False,
            platform_rules_reviewed=True,
        )
        result = evaluate_eligibility(review)
        self.assertFalse(result["eligible_for_manual_review"])
        self.assertEqual(result["missing_confirmations"], ["no_deposit_or_purchase"])
        self.assertFalse(result["automation_permitted"])

    def test_all_confirmations_allow_only_manual_review(self):
        review = EligibilityReview(True, True, True, True, True)
        result = evaluate_eligibility(review)
        self.assertTrue(result["eligible_for_manual_review"])
        self.assertEqual(result["missing_confirmations"], [])
        self.assertFalse(result["automation_permitted"])

    def test_rejects_truthy_non_boolean_values(self):
        with self.assertRaises(ValueError):
            EligibilityReview(country_eligible=1)

    def test_rejects_wrong_review_type(self):
        with self.assertRaises(TypeError):
            evaluate_eligibility({"country_eligible": True})



if __name__ == "__main__":
    unittest.main()
