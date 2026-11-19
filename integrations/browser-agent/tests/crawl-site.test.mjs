import test from "node:test";
import assert from "node:assert/strict";
import { crawlSameOriginSite } from "../crawl-site.mjs";

const origin = "https://games.example";

test("walks nested same-origin folders breadth-first and avoids loops", async () => {
  const graph = {
    [origin + "/"]: { title: "Home", navigationTargets: [
      { role: "link", name: "Arcade", href: origin + "/arcade" },
      { role: "link", name: "External", href: "https://other.example/" }
    ] },
    [origin + "/arcade"]: { title: "Arcade", navigationTargets: [
      { role: "link", name: "Puzzle", href: origin + "/arcade/puzzle" },
      { role: "link", name: "Home", href: origin + "/" }
    ] },
    [origin + "/arcade/puzzle"]: { title: "Puzzle", navigationTargets: [] }
  };
  let current;
  const result = await crawlSameOriginSite({
    startUrl: origin + "/",
    approvedOrigin: origin,
    openPage: async url => { current = url; },
    inspectPage: async () => graph[current]
  });
  assert.equal(result.status, "completed");
  assert.deepEqual(result.pages.map(page => page.url), [
    origin + "/", origin + "/arcade", origin + "/arcade/puzzle"
  ]);
});

test("honors maximum depth and page limits", async () => {
  const seen = [];
  const result = await crawlSameOriginSite({
    startUrl: origin + "/",
    approvedOrigin: origin,
    maxPages: 2,
    openPage: async url => { seen.push(url); },
    inspectPage: async () => ({ navigationTargets: [
      { role: "link", name: "Next", href: origin + (seen.length === 1 ? "/next" : "/third") }
    ] })
  });
  assert.equal(result.status, "limited");
  assert.equal(result.reason, "page_limit");
  assert.equal(seen.length, 2);
});

test("stops immediately on a verification gate", async () => {
  const result = await crawlSameOriginSite({
    startUrl: origin + "/",
    approvedOrigin: origin,
    openPage: async () => {},
    inspectPage: async () => ({ title: "Human verification", navigationTargets: [] }),
    isBlocked: observation => /verification/i.test(observation.title)
  });
  assert.equal(result.status, "human_required");
  assert.equal(result.pages.length, 0);
});

test("rejects a start URL outside the exact HTTPS origin", async () => {
  await assert.rejects(() => crawlSameOriginSite({
    startUrl: "http://games.example/",
    approvedOrigin: origin,
    openPage: async () => {},
    inspectPage: async () => ({})
  }), /approved HTTPS origin/);
});
