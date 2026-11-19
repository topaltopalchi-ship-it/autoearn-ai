import test from "node:test";
import assert from "node:assert/strict";
import "../static/discovery-provenance.js";

test("extracts discovery source, search query, timestamp and excerpt", () => {
  const notes = "Existing notes.\n[DISCOVERY PROVENANCE]\n" + JSON.stringify({
    source: "Mwmbl search",
    search_query: "free cash prize game",
    discovered_at: "2026-11-19T10:00:00.000Z",
    excerpt: "Official rules mention a free contest."
  });
  assert.deepEqual(
    globalThis.AutoEarnDiscoveryProvenance.extractDiscoveryProvenance(notes),
    {
      source: "Mwmbl search",
      search_query: "free cash prize game",
      discovered_at: "2026-11-19T10:00:00.000Z",
      excerpt: "Official rules mention a free contest."
    }
  );
});

test("returns null when discovery provenance is absent or malformed", () => {
  assert.equal(globalThis.AutoEarnDiscoveryProvenance.extractDiscoveryProvenance("No marker"), null);
  assert.equal(globalThis.AutoEarnDiscoveryProvenance.extractDiscoveryProvenance("[DISCOVERY PROVENANCE]\n{bad json}"), null);
});

test("bounds imported provenance text lengths", () => {
  const notes = "[DISCOVERY PROVENANCE]\n" + JSON.stringify({
    source: "s".repeat(100),
    search_query: "q".repeat(500),
    discovered_at: "d".repeat(80),
    excerpt: "e".repeat(2000)
  });
  const parsed = globalThis.AutoEarnDiscoveryProvenance.extractDiscoveryProvenance(notes);
  assert.equal(parsed.source.length, 80);
  assert.equal(parsed.search_query.length, 240);
  assert.equal(parsed.discovered_at.length, 40);
  assert.equal(parsed.excerpt.length, 900);
});
