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

test("expands a safe folder button and discovers newly revealed links", async () => {
  let current = origin + "/";
  let expanded = false;
  const visited = [];
  const result = await crawlSameOriginSite({
    startUrl: origin + "/",
    approvedOrigin: origin,
    openPage: async url => { current = url; visited.push(url); },
    inspectPage: async () => current === origin + "/" && !expanded
      ? {
          title: "Arcade Categories",
          navigationTargets: [{ role: "button", name: "Puzzle category" }]
        }
      : current === origin + "/puzzle"
        ? { title: "Puzzle Game", snapshot: "canvas Score: 5", navigationTargets: [] }
        : {
            title: "Arcade Categories",
            navigationTargets: [
              { role: "button", name: "Puzzle category" },
              { role: "link", name: "Puzzle game", href: origin + "/puzzle" }
            ]
          },
    expandFolderButton: async name => {
      assert.equal(name, "Puzzle category");
      expanded = true;
      return true;
    }
  });
  assert.deepEqual(visited, [origin + "/", origin + "/puzzle"]);
  assert.deepEqual(result.pages[0].expandedButtons, ["Puzzle category"]);
  assert.equal(result.pages[1].classification.type, "game");
});

test("attaches explicit known-game detection without guessing from labels", async () => {
  const cells = Array.from({ length: 9 }, (_, index) => ({ index, mark: "" }));
  const result = await crawlSameOriginSite({
    startUrl: origin + "/ttt",
    approvedOrigin: origin,
    openPage: async () => {},
    inspectPage: async () => ({
      title: "Puzzle",
      snapshot: "play game score",
      navigationTargets: [],
      gameCandidates: [{ kind: "tic-tac-toe", boardKey: "board-1", cells }]
    })
  });
  assert.equal(result.pages[0].gameDetection.gameType, "tic-tac-toe");
  assert.equal(result.pages[0].gameDetection.reason, "explicit_board_signature");
});


test("does not queue same-origin URLs containing embedded credentials", async () => {
  const seen = [];
  const result = await crawlSameOriginSite({
    startUrl: origin + "/",
    approvedOrigin: origin,
    openPage: async url => { seen.push(url); },
    inspectPage: async () => ({ navigationTargets: [
      { role: "link", name: "Credential URL", href: "https://user:secret@games.example/private" },
      { role: "link", name: "Nonstandard port", href: "https://games.example:8443/private" }
    ] })
  });
  assert.deepEqual(seen, [origin + "/"]);
  assert.equal(result.status, "completed");
});


test("rejects a start URL containing embedded credentials", async () => {
  await assert.rejects(() => crawlSameOriginSite({
    startUrl: "https://user:secret@games.example/",
    approvedOrigin: origin,
    openPage: async () => {},
    inspectPage: async () => ({})
  }), /approved HTTPS origin/);
});

test("rejects a start URL using a nonstandard port", async () => {
  await assert.rejects(() => crawlSameOriginSite({
    startUrl: "https://games.example:8443/",
    approvedOrigin: origin,
    openPage: async () => {},
    inspectPage: async () => ({})
  }), /approved HTTPS origin/);
});
