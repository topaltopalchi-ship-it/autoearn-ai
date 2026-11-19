import test from "node:test";
import assert from "node:assert/strict";
import "../static/due-diligence.js";

test("extracts due-diligence alerts from discovery notes", () => {
  const notes = "Payout hints: unverified. Due-diligence flags: identity_verification_mentioned, minimum_withdrawal_not_found. Country is not filtered.";
  assert.equal(
    globalThis.AutoEarnDueDiligence.extractReviewFlags(notes),
    "identity_verification_mentioned, minimum_withdrawal_not_found",
  );
});

test("returns empty text when no due-diligence alert marker exists", () => {
  assert.equal(globalThis.AutoEarnDueDiligence.extractReviewFlags("No alerts recorded."), "");
});

test("scores evidence completeness without treating the score as verification", () => {
  const notes = "Due-diligence flags: prize_amount_not_found, organizer_identity_not_found, specific_payout_method_not_found. Review manually.";
  const result = globalThis.AutoEarnDueDiligence.calculateEvidenceCompleteness(notes, "");
  assert.deepEqual(result, {
    score: 45,
    missing: ["prize_amount_not_found", "organizer_identity_not_found", "specific_payout_method_not_found"],
    officialTermsProvided: false,
  });
});

test("clean text signals score 90 without official terms and 100 when terms are linked", () => {
  const notes = "Due-diligence flags: no missing details detected by text heuristics. Review manually.";
  assert.equal(globalThis.AutoEarnDueDiligence.calculateEvidenceCompleteness(notes, "").score, 90);
  assert.equal(globalThis.AutoEarnDueDiligence.calculateEvidenceCompleteness(notes, "https://example.com/terms").score, 100);
});

test("returns null when no discovery due-diligence result exists", () => {
  assert.equal(globalThis.AutoEarnDueDiligence.calculateEvidenceCompleteness("No flags", ""), null);
});

test("does not mistake the explanatory clean-flags sentence for an alert", () => {
  const notes = "Due-diligence flags: no missing details detected by text heuristics. Confirm official terms.";
  assert.equal(
    globalThis.AutoEarnDueDiligence.extractReviewFlags(notes),
    "no missing details detected by text heuristics",
  );
});
