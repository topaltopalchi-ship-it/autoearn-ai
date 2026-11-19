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
      const scoreA = evidenceScore(a);
      const scoreB = evidenceScore(b);
      if ((scoreA < 0) !== (scoreB < 0)) return scoreA < 0 ? 1 : -1;
      const delta = scoreB - scoreA;
      if (delta !== 0) return mode === "evidence-low" ? -delta : delta;
      return String(b?.created_at || "").localeCompare(String(a?.created_at || ""));
    });
    return rows;
  }

  function safePublicHttpsUrl(value) {
    try {
      const url = new URL(String(value || "").trim());
      const host = url.hostname.toLowerCase().replace(/\\.$/, "");
      if (url.protocol !== "https:" || url.username || url.password || (url.port && url.port !== "443")) return null;
      if (!host || host === "localhost" || host.endsWith(".localhost") || host.endsWith(".local") || host.startsWith("[") || /^\\d{1,3}(?:\\.\\d{1,3}){3}$/.test(host)) return null;
      const labels = host.split(".");
      if (labels.length < 2 || labels.some((label) => !label || label.length > 63 || !/^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$/.test(label))) return null;
      return url.href;
    } catch (_) {
      return null;
    }
  }

  function formatCategoryLabels(category, labels = {}) {
    const values = String(category || "").split(",").map((value) => value.trim()).filter(Boolean);
    return values.map((value) => labels[value] || value).join(", ") || "Other";
  }

  function summarizeOpportunities(opportunities) {
    const rows = Array.isArray(opportunities) ? opportunities : [];
    const scored = rows
      .map((item) => calculateEvidenceCompleteness(item?.notes, item?.terms_url))
      .filter(Boolean);
    const counts = { high: 0, medium: 0, low: 0, unscored: rows.length - scored.length };
    for (const item of scored) {
      if (item.score >= 80) counts.high++;
      else if (item.score >= 50) counts.medium++;
      else counts.low++;
    }
    return {
      total: rows.length,
      scored: scored.length,
      counts,
      averageScore: scored.length
        ? Math.round(scored.reduce((sum, item) => sum + item.score, 0) / scored.length)
        : null,
    };
  }

  root.AutoEarnDueDiligence = Object.freeze({
    extractReviewFlags,
    calculateEvidenceCompleteness,
    sortOpportunities,
    summarizeOpportunities,
    formatCategoryLabels,
    safePublicHttpsUrl,
  });
})(globalThis);
