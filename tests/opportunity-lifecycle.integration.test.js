import test from "node:test";
import assert from "node:assert/strict";
import "../static/discovery-provenance.js";
import "../static/due-diligence.js";
import "../static/reward-ledger.js";
import "../static/opportunity-economics.js";

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


test("end-to-end review keeps discovered leads unverified while economics and reward records stay separate", () => {
  const economics = globalThis.AutoEarnOpportunityEconomics;
  const discoveredNotes = [
    "Due-diligence flags: official_source_not_verified, official_terms_source_not_verified.",
    "[DISCOVERY PROVENANCE]",
    JSON.stringify({
      source: "Mwmbl search",
      search_query: "cash game rewards",
      discovered_at: "2026-11-20T08:00:00.000Z",
      excerpt: "A search result mentions a cash reward."
    })
  ].join("\n");

  const report = {
    reviewed_at: "2026-11-20T08:30:00.000Z",
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
    automation_source: "https://publisher.example.org/automation",
    estimated_economics: {
      reward_amount: 20,
      currency: "USD",
      success_probability: 0.7,
      time_hours: 2,
      direct_costs: 3
    }
  };
  const reviewedNotes = diligence.replaceOwnerEligibilityReview(discoveredNotes, report);
  const opportunity = {
    id: "candidate-1",
    status: "eligible",
    url: "https://publisher.example.org/",
    terms_url: "https://publisher.example.org/rules",
    notes: reviewedNotes,
    created_at: "2026-11-20T08:00:00.000Z"
  };

  const evidence = diligence.calculateEvidenceCompleteness(opportunity.notes, opportunity.terms_url);
  assert.equal(evidence.officialTermsVerified, false);
  assert.equal(evidence.organizerIdentityVerified, false);
  assert.equal(diligence.getEligibilityReviewStatus(report), "reviewing");
  assert.equal(diligence.canStartGuidedSession(opportunity), false);

  const estimate = economics.extractOwnerEstimate(opportunity.notes);
  assert.equal(estimate.expectedNet, 11);
  assert.equal(estimate.expectedNetPerHour, 5.5);
  assert.equal(economics.sortByExpectedHourlyValue([opportunity])[0].id, "candidate-1");

  const pendingReward = { amount: 11, currency: "USD", status: "pending", reference: "" };
  assert.equal(ledger.validateReward(pendingReward), "");
  assert.equal(ledger.summarize([pendingReward]).pending.length, 1);
  assert.match(ledger.validateReward({ ...pendingReward, status: "paid" }), /reference/i);
  assert.equal(ledger.summarize([{ ...pendingReward, status: "paid" }]).paid.length, 0);
});
