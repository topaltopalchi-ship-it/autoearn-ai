(function (root) {
  "use strict";

  const PENALTIES = Object.freeze({
    official_source_not_verified: 15,
    official_terms_source_not_verified: 15,
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
      officialTermsVerified: false,
      organizerIdentityVerified: false,
    };
  }

  function classifyEntryCost(item) {
    const text = [item?.title, item?.platform, item?.reward_description, item?.eligibility, item?.notes]
      .filter(Boolean).join(" ").toLowerCase().replace(/[‐‑‒–—]/g, "-");
    const free = /\b(?:free[- ](?:to[- ]play|entry|registration)|no (?:purchase|entry fee|deposit|payment) (?:necessary|required)|without (?:an? )?entry fee|zero entry fee)\b/.test(text);
    const paid = /\b(?:paid entry|entry fee|buy[- ]in|purchase required|deposit required|pay to enter|paid registration|subscription required)\b/.test(text);
    if (free && !paid) return "free";
    if (paid && !free) return "paid";
    return "unknown";
  }

  function classifyOpportunityType(item) {
    const text = [item?.title, item?.platform, item?.url, item?.category, item?.reward_description, item?.eligibility, item?.notes]
      .filter(Boolean).join(" ").toLowerCase();
    const businessService = /\b(?:payment processor|payment gateway|accept payments|business payments|merchant services|invoice(?:s|ing)? software|accounting software|website builder|e-?commerce platform|online store builder|customer relationship management|crm|marketing automation|advertising platform|business management software|point of sale|pos system|web hosting provider)\b/.test(text);
    const normalizedUrl = String(item?.url || "").toLowerCase().replace(/^https?:\/\//, "");
    const knownServiceDomain = /(?:^|\.)paypal\.com(?:$|\/)|(?:^|\.)stripe\.com(?:$|\/)|(?:^|\.)squareup\.com(?:$|\/)/.test(normalizedUrl);
    if (businessService || knownServiceDomain) return "irrelevant";
    return "review";
  }

  function sortOpportunities(opportunities, mode = "evidence") {
    const rows = Array.isArray(opportunities) ? [...opportunities] : [];
    const evidenceScore = (item) =>
      calculateEvidenceCompleteness(item?.notes, item?.terms_url)?.score ?? -1;
    rows.sort((a, b) => {
      const costRank = { free: 0, unknown: 1, paid: 2 };
      const costDelta = costRank[classifyEntryCost(a)] - costRank[classifyEntryCost(b)];
      if (costDelta !== 0) return costDelta;
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
      const host = url.hostname.toLowerCase().replace(/\.$/, "");
      if (url.protocol !== "https:" || url.username || url.password || (url.port && url.port !== "443")) return null;
      if (!host || host === "localhost" || [".localhost", ".local", ".internal", ".test", ".invalid", ".example"].some((suffix) => host.endsWith(suffix)) || host.startsWith("[") || /^\d{1,3}(?:\.\d{1,3}){3}$/.test(host)) return null;
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

  function canStartGuidedSession(opportunity) {
    // This gate only enables a user-initiated visit to a public HTTPS page.
    // It never authorizes automated gameplay, account actions, or payments.
    return opportunity?.status === "eligible" && Boolean(safePublicHttpsUrl(opportunity?.url));
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
    classifyEntryCost,
    summarizeOpportunities,
    formatCategoryLabels,
    safePublicHttpsUrl,
    canStartGuidedSession,
  });
})(globalThis);
