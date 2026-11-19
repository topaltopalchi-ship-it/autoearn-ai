(function (root) {
  "use strict";

  const PENALTIES = Object.freeze({
    minimum_withdrawal_not_found: 12,
    specific_payout_method_not_found: 10,
    withdrawal_fees_not_found: 8,
    prize_amount_not_found: 15,
    payout_timing_not_found: 10,
    organizer_identity_not_found: 20,
    winner_selection_method_not_found: 8,
  });

  function extractReviewFlags(notes) {
    const match = String(notes || "").match(/Due-diligence flags: ([^.]+)\./);
    return match ? match[1].trim() : "";
  }

  function calculateEvidenceCompleteness(notes, termsUrl) {
    const raw = extractReviewFlags(notes);
    if (!raw) return null;
    const flags = raw === "no missing details detected by text heuristics"
      ? []
      : raw.split(",").map((flag) => flag.trim()).filter(Boolean);
    const missing = flags.filter((flag) => Object.hasOwn(PENALTIES, flag));
    const termsMissing = !String(termsUrl || "").trim();
    const penalty = missing.reduce((sum, flag) => sum + PENALTIES[flag], 0) + (termsMissing ? 10 : 0);
    return {
      score: Math.max(0, 100 - penalty),
      missing,
      officialTermsProvided: !termsMissing,
    };
  }

  function sortOpportunities(opportunities, mode = "evidence") {
    const rows = Array.isArray(opportunities) ? [...opportunities] : [];
    const evidenceScore = (item) =>
      calculateEvidenceCompleteness(item?.notes, item?.terms_url)?.score ?? -1;
    rows.sort((a, b) => {
      if (mode === "newest") {
        return String(b?.created_at || "").localeCompare(String(a?.created_at || ""));
      }
      const delta = evidenceScore(b) - evidenceScore(a);
      if (delta !== 0) return mode === "evidence-low" ? -delta : delta;
      return String(b?.created_at || "").localeCompare(String(a?.created_at || ""));
    });
    return rows;
  }

  root.AutoEarnDueDiligence = Object.freeze({
    extractReviewFlags,
    calculateEvidenceCompleteness,
    sortOpportunities,
  });
})(globalThis);
