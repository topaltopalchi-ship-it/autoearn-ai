(function (root) {
  "use strict";
  function extractDiscoveryProvenance(notes) {
    const match = String(notes || "").match(/\\[DISCOVERY PROVENANCE\\]\\s*(\\{[^\\n]*\\})/);
    if (!match) return null;
    try {
      const value = JSON.parse(match[1]);
      if (!value || typeof value !== "object" || Array.isArray(value)) return null;
      return {
        source: typeof value.source === "string" ? value.source.slice(0, 80) : "",
        search_query: typeof value.search_query === "string" ? value.search_query.slice(0, 240) : "",
        discovered_at: typeof value.discovered_at === "string" ? value.discovered_at.slice(0, 40) : "",
        excerpt: typeof value.excerpt === "string" ? value.excerpt.slice(0, 900) : ""
      };
    } catch (_) { return null; }
  }
  root.AutoEarnDiscoveryProvenance = Object.freeze({ extractDiscoveryProvenance });
})(globalThis);
