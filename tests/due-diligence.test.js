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

test("penalizes unverified organizer domain and official terms in discovery evidence", () => {
  const notes = "Due-diligence flags: official_source_not_verified, official_terms_source_not_verified. Review manually.";
  const result = globalThis.AutoEarnDueDiligence.calculateEvidenceCompleteness(notes, "");
  assert.deepEqual(result, {
    score: 60,
    missing: ["official_source_not_verified", "official_terms_source_not_verified"],
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
    counts: { high: 1, medium: 2, low: 0, unscored: 1 },
    averageScore: 77,
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
  assert.deepEqual(
    globalThis.AutoEarnDueDiligence.sortOpportunities([manual, discovered], "evidence-low").map((item) => item.id),
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

test("formats merged opportunity categories with readable labels", () => {
  const labels = { game: "Game", contest: "Contest", puzzle: "Puzzle" };
  assert.equal(
    globalThis.AutoEarnDueDiligence.formatCategoryLabels("game, contest, puzzle", labels),
    "Game, Contest, Puzzle",
  );
  assert.equal(globalThis.AutoEarnDueDiligence.formatCategoryLabels("", labels), "Other");
});

test("accepts public HTTPS URLs and normalizes them", () => {
  assert.equal(
    globalThis.AutoEarnDueDiligence.safePublicHttpsUrl(" https://Example.com/path "),
    "https://example.com/path",
  );
  assert.equal(
    globalThis.AutoEarnDueDiligence.safePublicHttpsUrl("https://example.com:443/terms"),
    "https://example.com/terms",
  );
});

test("rejects unsafe schemes, credentials, local hosts, IP literals, and nonstandard ports", () => {
  const validate = globalThis.AutoEarnDueDiligence.safePublicHttpsUrl;
  for (const value of [
    "javascript:alert(1)",
    "http://example.com",
    "https://user:pass@example.com",
    "https://localhost",
    "https://sub.localhost",
    "https://service.local",
    "https://127.0.0.1",
    "https://192.168.1.10",
    "https://example.com:8443",
    "not a URL",
  ]) {
    assert.equal(validate(value), null, value);
  }
});

test("replaces an earlier owner eligibility review instead of accumulating invalid JSON", () => {
  const replace = globalThis.AutoEarnDueDiligence.replaceOwnerEligibilityReview;
  const first = { reviewed_at: "2026-11-01T00:00:00.000Z", payment_method: "PayPal" };
  const second = { reviewed_at: "2026-11-19T00:00:00.000Z", payment_method: "Bank transfer" };
  const initial = replace("Original opportunity notes", first);
  const updated = replace(initial, second);
  assert.match(updated, /^Original opportunity notes\n\n\[OWNER OFFICIAL ELIGIBILITY REVIEW\]/);
  assert.equal((updated.match(/\[OWNER OFFICIAL ELIGIBILITY REVIEW\]/g) || []).length, 1);
  const json = updated.slice(updated.indexOf("[OWNER OFFICIAL ELIGIBILITY REVIEW]") + "[OWNER OFFICIAL ELIGIBILITY REVIEW]".length).trim();
  assert.deepEqual(JSON.parse(json), second);
});

test("rejects unknown or placeholder values in owner eligibility details", () => {
  const known = globalThis.AutoEarnDueDiligence.hasKnownReviewValue;
  for (const value of ["", "   ", "Not stated", " UNKNOWN ", "n/a", "NA", "not available", "unspecified", "to be confirmed", "TBD", "-", "—", "Not   stated", "Not\t stated"]) {
    assert.equal(known(value), false, JSON.stringify(value));
  }
  for (const value of ["10 USD", "18", "0%", "No fee", "Required"]) {
    assert.equal(known(value), true, value);
  }
});

test("keeps unknown eligibility under review and disqualifies only explicit blockers", () => {
  const status = globalThis.AutoEarnDueDiligence.getEligibilityReviewStatus;
  assert.equal(status({ payment_confirmed: "unknown", country_eligible: "unknown", free_entry: "unknown" }), "reviewing");
  assert.equal(status({ payment_confirmed: "yes", country_eligible: "yes", free_entry: "yes", automation: "unknown" }), "reviewing");
  assert.equal(status({ payment_confirmed: "yes", country_eligible: "yes", free_entry: "yes", automation: "no" }), "reviewing");
  assert.equal(status({ payment_confirmed: "no", country_eligible: "yes", free_entry: "yes" }), "ineligible");
  assert.equal(status({ payment_confirmed: "yes", country_eligible: "no", free_entry: "yes" }), "ineligible");
  assert.equal(status({ payment_confirmed: "yes", country_eligible: "yes", free_entry: "no" }), "ineligible");
});

test("guided sessions require an explicitly eligible opportunity status", () => {
  const canStart = globalThis.AutoEarnDueDiligence.canStartGuidedSession;
  for (const status of ["discovered", "reviewing", "ineligible", "archived", "pending", "approved", "", null]) {
    assert.equal(canStart({ status }), false, String(status));
  }
  assert.equal(canStart({ status: "eligible" }), false);
  assert.equal(canStart(null), false);
  assert.equal(canStart(undefined), false);
});


test("guided session gate rejects malformed and structurally invalid review reports", () => {
  const canStart = globalThis.AutoEarnDueDiligence.canStartGuidedSession;
  const report = {
    payment_method: "PayPal",
    payment_confirmed: "yes",
    minimum_withdrawal: "10 USD",
    fees: "0%",
    country_eligible: "yes",
    minimum_age: "18",
    kyc: "required",
    free_entry: "yes",
    automation_explicitly_allowed: "yes",
    payout_source: "https://example.com/payout",
    automation_source: "https://example.com/automation"
  };
  const opportunity = (notes, overrides = {}) => ({
    status: "eligible",
    terms_url: "https://example.com/terms",
    notes: "[OWNER OFFICIAL ELIGIBILITY REVIEW]\n" + notes,
    ...overrides
  });
  for (const notes of ["{", "null", "[]", '"yes"', JSON.stringify({ ...report, kyc: "maybe" }), JSON.stringify({ ...report, payment_method: "Other / not specified" }), JSON.stringify({ ...report, minimum_age: "unknown" }), JSON.stringify({ ...report, payout_source: "http://example.com/payout" }), JSON.stringify({ ...report, automation_source: "https://localhost/rules" })]) {
    assert.equal(canStart(opportunity(notes)), false, notes);
  }
  assert.equal(canStart(opportunity(JSON.stringify(report), { terms_url: "https://example.com:8443/terms" })), false);
  assert.equal(canStart(opportunity(JSON.stringify(report), { notes: "[OWNER OFFICIAL ELIGIBILITY REVIEW]\n" + JSON.stringify(report) + "\ntrailing text" })), false);
});
test("owner self-attestation and valid HTTPS links never count as independent verification", () => {
  const canStart = globalThis.AutoEarnDueDiligence.canStartGuidedSession;
  const valid = {
    status: "eligible",
    terms_url: "https://example.com/terms",
    notes: "[OWNER OFFICIAL ELIGIBILITY REVIEW]\n" + JSON.stringify({
      payment_method: "PayPal",
      payment_confirmed: "yes",
      minimum_withdrawal: "10 USD",
      fees: "0%",
      country_eligible: "yes",
      minimum_age: "18",
      kyc: "required",
      free_entry: "yes",
      automation_explicitly_allowed: "yes",
      payout_source: "https://example.com/payout",
      automation_source: "https://example.com/automation"
    })
  };
  assert.equal(canStart({ status: "eligible" }), false);
  assert.equal(canStart({ ...valid, notes: valid.notes.replace(/("fees"\s*:\s*)"0%"/, '$1"Not stated"') }), false);
  assert.equal(canStart({ ...valid, notes: valid.notes.replace(/("automation_explicitly_allowed"\s*:\s*)"yes"/, '$1"unknown"') }), false);
  assert.equal(canStart({ ...valid, terms_url: "javascript:alert(1)" }), false);
  assert.equal(canStart(valid), false);
});
