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

test("does not mistake the explanatory clean-flags sentence for an alert", () => {
  const notes = "Due-diligence flags: no missing details detected by text heuristics. Confirm official terms.";
  assert.equal(
    globalThis.AutoEarnDueDiligence.extractReviewFlags(notes),
    "no missing details detected by text heuristics",
  );
});
