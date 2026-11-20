import test from "node:test";
import assert from "node:assert/strict";
import "../static/discovery-provenance.js";
import "../static/due-diligence.js";
import "../static/reward-ledger.js";

const provenance = globalThis.AutoEarnDiscoveryProvenance;
const diligence = globalThis.AutoEarnDueDiligence;
const ledger = globalThis.AutoEarnRewardLedger;

test("discovery evidence flows into review without becoming independent verification", () => {
  const notes = [
    "Due-diligence flags: official_source_not_verified, official_terms_source_not_verified.",
    "[DISCOVERY PROVENANCE]",
    JSON.stringify({
      source: "Mwmbl search",
      search_query: "free cash game",
      discovered_at: "2026-11-20T08:00:00.000Z",
      excerpt: "Search snippet mentions a cash reward."
    })
  ].join("\n");
  const source = provenance.extractDiscoveryProvenance(notes);
  assert.equal(source.source, "Mwmbl search");
  assert.equal(source.search_query, "free cash game");

  const evidence = diligence.calculateEvidenceCompleteness(notes, "https://publisher.example.org/rules");
  assert.equal(evidence.score, 70);
  assert.equal(evidence.officialTermsProvided, true);
  assert.equal(evidence.officialTermsVerified, false);
  assert.equal(evidence.organizerIdentityVerified, false);
});

test("owner checklist and public URLs cannot open the guided-session gate", () => {
  const report = {
    reviewed_at: "2026-11-20T08:00:00.000Z",
    payment_method: "PayPal",
    payment_confirmed: "yes",
    minimum_withdrawal: "10 USD",
    fees: "0%",
    country_eligible: "yes",
    minimum_age: "18",
    kyc: "not-required",
    free_entry: "yes",
    automation_explicitly_allowed: "yes",
    payout_source: "https://publisher.example.org/payout",
    automation_source: "https://publisher.example.org/automation"
  };
  const notes = diligence.replaceOwnerEligibilityReview("Owner-entered candidate", report);
  const opportunity = {
    status: "eligible",
    url: "https://publisher.example.org/",
    terms_url: "https://publisher.example.org/rules",
    notes
  };
  assert.equal(diligence.getEligibilityReviewStatus(report), "reviewing");
  assert.equal(diligence.safePublicHttpsUrl(opportunity.terms_url), opportunity.terms_url);
  assert.equal(diligence.canStartGuidedSession(opportunity), false);
});

test("reward ledger distinguishes pending, confirmed and evidenced paid amounts", () => {
  const rows = [
    { amount: 12, currency: "USD", status: "pending" },
    { amount: 5, currency: "EUR", status: "confirmed" },
    { amount: 90, currency: "USD", status: "paid", reference: "" },
    { amount: 7, currency: "USD", status: "paid", reference: "TX-verified-by-owner" }
  ];
  const summary = ledger.summarize(rows);
  assert.deepEqual(summary.pending.map(row => row.amount), [12]);
  assert.deepEqual(summary.confirmed.map(row => row.amount), [5]);
  assert.deepEqual(summary.paid.map(row => row.amount), [7]);
  assert.match(ledger.validateReward({ amount: 7, currency: "USD", status: "paid", reference: "" }), /reference/i);
  assert.equal(ledger.validateReward({ amount: 7, currency: "USD", status: "paid", reference: "TX-1" }), "");
});
