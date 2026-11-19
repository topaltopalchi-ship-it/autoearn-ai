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

test("sorts opportunities by evidence completeness without mutating input", () => {
  const low = {
    id: 1,
    created_at: "2026-01-01",
    notes: "Due-diligence flags: organizer_identity_not_found, prize_amount_not_found.",
    terms_url: "",
  };
  const high = {
    id: 2,
    created_at: "2026-01-02",
    notes: "Due-diligence flags: no missing details detected by text heuristics.",
    terms_url: "https://example.com/terms",
  };
  const input = [low, high];
  assert.deepEqual(
    globalThis.AutoEarnDueDiligence.sortOpportunities(input, "evidence").map((item) => item.id),
    [2, 1],
  );
  assert.deepEqual(input.map((item) => item.id), [1, 2]);
  assert.deepEqual(
    globalThis.AutoEarnDueDiligence.sortOpportunities(input, "evidence-low").map((item) => item.id),
    [1, 2],
  );
  assert.deepEqual(
    globalThis.AutoEarnDueDiligence.sortOpportunities(input, "newest").map((item) => item.id),
    [2, 1],
  );
});

test("summarizes evidence completeness bands and excludes unscored entries from average", () => {
  const rows = [
    { notes: "Due-diligence flags: no missing details detected by text heuristics.", terms_url: "https://example.com/terms" },
    { notes: "Due-diligence flags: prize_amount_not_found, organizer_identity_not_found.", terms_url: "" },
    { notes: "Due-diligence flags: prize_amount_not_found.", terms_url: "" },
    { notes: "Owner notes only", terms_url: "" },
  ];
  assert.deepEqual(globalThis.AutoEarnDueDiligence.summarizeOpportunities(rows), {
    total: 4,
    scored: 3,
    counts: { high: 1, medium: 0, low: 2, unscored: 1 },
    averageScore: 72,
  });
});

test("returns null average when there are no scored opportunities", () => {
  assert.deepEqual(globalThis.AutoEarnDueDiligence.summarizeOpportunities([{ notes: "manual", terms_url: "" }]), {
    total: 1,
    scored: 0,
    counts: { high: 0, medium: 0, low: 0, unscored: 1 },
    averageScore: null,
  });
});

test("unscored manual entries sort after scored discovery candidates", () => {
  const manual = { id: "manual", notes: "Owner-entered notes", terms_url: "" };
  const discovered = {
    id: "discovered",
    notes: "Due-diligence flags: no missing details detected by text heuristics.",
    terms_url: "https://example.com/terms",
  };
  assert.deepEqual(
    globalThis.AutoEarnDueDiligence.sortOpportunities([manual, discovered]).map((item) => item.id),
    ["discovered", "manual"],
  );
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
