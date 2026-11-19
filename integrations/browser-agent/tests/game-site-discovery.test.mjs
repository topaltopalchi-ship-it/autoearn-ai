import test from "node:test";
import assert from "node:assert/strict";
import { discoverSupportedGame, selectGameNavigationLinks } from "../game-site-discovery.mjs";

test("follows only same-origin game and folder links, rejecting account and external links", () => {
  const links = selectGameNavigationLinks([
    { href: "/games", label: "Games" },
    { href: "/folder/arcade", label: "Open folder" , folderLink: true},
    { href: "https://other.example/games", label: "Games" },
    { href: "/account/login", label: "Game login" },
    { href: "/news", label: "News" },
    { href: "/puzzle?token=private#board", label: "Puzzle" }
  ], { baseUrl: "https://site.example/home", origin: "https://site.example" });
  assert.deepEqual(links.map(item => item.url), [
    "https://site.example/games",
    "https://site.example/folder/arcade",
    "https://site.example/puzzle"
  ]);
});

function fakePage(startUrl, routes) {
  let current = startUrl;
  const getRoute = () => routes[new URL(current).pathname] || {};
  const body = {
    innerText: async () => getRoute().text || "",
    evaluate: async () => getRoute().candidates || []
  };
  return {
    url: () => current,
    isClosed: () => false,
    title: async () => getRoute().title || "",
    locator: selector => selector === "body" ? body : {
      evaluateAll: async () => (getRoute().links || []).map(link => ({
        href: new URL(link.href, current).href,
        label: link.label || "",
        title: "",
        ariaLabel: "",
        gameLink: Boolean(link.gameLink),
        folderLink: Boolean(link.folderLink)
      }))
    },
    goto: async url => { current = url; }
  };
}

const ttt = Array.from({ length: 9 }, (_, index) => ({
  index, mark: index === 0 ? "X" : ""
}));

test("finds a supported board inside a same-origin nested folder and selects its URL", async () => {
  const start = "https://site.example/home";
  const page = fakePage(start, {
    "/home": { title: "Home", links: [{ href: "/folder/arcade", label: "Arcade folder" }] },
    "/folder/arcade": { title: "Arcade", links: [{ href: "/games/ttt", label: "Tic Tac Toe" }] },
    "/games/ttt": { title: "Tic Tac Toe", candidates: [{ kind: "tic-tac-toe", boardKey: "main", cells: ttt }] }
  });
  const result = await discoverSupportedGame(page, { maxPages: 8, maxDepth: 2 });
  assert.equal(result.selected.url, "https://site.example/games/ttt");
  assert.equal(result.selected.detection.gameType, "tic-tac-toe");
  assert.equal(page.url(), result.selected.url);
});

test("detects a 42-cell Connect Four board inside a nested game folder", async () => {
  const start = "https://site.example/home";
  const cells = Array.from({ length: 42 }, (_, index) => ({ index, mark: index === 41 ? "X" : "" }));
  const page = fakePage(start, {
    "/home": { links: [{ href: "/games/board", label: "Games" }] },
    "/games/board": { candidates: [{ kind: "connect-four", boardKey: "cf", cells }] }
  });
  const result = await discoverSupportedGame(page);
  assert.equal(result.selected.detection.gameType, "connect-four");
  assert.equal(page.url(), "https://site.example/games/board");
});

test("refuses to choose when multiple supported games are found", async () => {
  const start = "https://site.example/home";
  const page = fakePage(start, {
    "/home": { links: [
      { href: "/games/a", label: "Game A" },
      { href: "/games/b", label: "Game B" }
    ] },
    "/games/a": { candidates: [{ kind: "tic-tac-toe", cells: ttt }] },
    "/games/b": { candidates: [{ kind: "2048", tiles: [{x:0,y:0,value:2},{x:1,y:1,value:4}] }] }
  });
  const result = await discoverSupportedGame(page);
  assert.equal(result.selected, null);
  assert.equal(result.ambiguous, true);
  assert.equal(page.url(), start);
});

test("stops at a verification gate and does not continue crawling", async () => {
  const start = "https://site.example/home";
  const page = fakePage(start, {
    "/home": { links: [{ href: "/games/a", label: "Games" }] },
    "/games/a": { title: "Security challenge", text: "Are you human? CAPTCHA" }
  });
  await assert.rejects(() => discoverSupportedGame(page), /Verification or anti-bot gate/);
});
