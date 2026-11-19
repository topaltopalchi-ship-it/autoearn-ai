import test from "node:test";
import assert from "node:assert/strict";
import { discoverGameInstructions, selectInstructionLinks } from "../game-instruction-discovery.mjs";

test("selects only clearly-labelled same-origin HTTPS help pages", () => {
  const links = selectInstructionLinks([
    { href: "/help", label: "Help" },
    { href: "https://other.example/rules", label: "Rules" },
    { href: "/account/logout", label: "Help" },
    { href: "/news", label: "Latest news" },
    { href: "/manual/game?session=private#top", label: "Game manual" }
  ], { baseUrl: "https://game.example/play", origin: "https://game.example", maxLinks: 5 });
  assert.deepEqual(links.map(item => item.url), [
    "https://game.example/help",
    "https://game.example/manual/game"
  ]);
});

function fakePage(initialUrl, pages) {
  let current = initialUrl;
  const pageData = () => pages[new URL(current).pathname] || { title: "", text: "", snapshot: "", links: [] };
  const body = {
    innerText: async () => pageData().text,
    ariaSnapshot: async () => pageData().snapshot
  };
  return {
    url: () => current,
    isClosed: () => false,
    title: async () => pageData().title,
    mainFrame: () => main,
    frames: () => [main],
    locator: selector => selector === "body" ? body : {
      evaluateAll: async () => pageData().links.map(link => ({
        href: new URL(link.href, current).href,
        innerText: link.label,
        getAttribute: name => name === "title" ? "" : null
      }))
    },
    goto: async url => { current = url; },
  };
}
const main = { url: () => "https://game.example/play" };

test("reads a same-origin rules page and returns to the game URL", async () => {
  const start = "https://game.example/play";
  const pages = {
    "/play": {
      title: "Puzzle",
      text: "Welcome to the puzzle.",
      snapshot: "Game board",
      links: [{ href: "/instructions", label: "How to play" }]
    },
    "/instructions": {
      title: "Instructions",
      text: "Use arrow keys to move tiles and reach the target.",
      snapshot: "Instructions"
    }
  };
  const page = fakePage(start, pages);
  const result = await discoverGameInstructions(page);
  assert.equal(result.pages.length, 2);
  assert.match(result.text, /Use arrow keys/);
  assert.equal(page.url(), start);
});

test("does not visit external links and never clicks arbitrary controls", async () => {
  const start = "https://game.example/play";
  const pages = {
    "/play": {
      title: "Puzzle",
      text: "Play",
      links: [{ href: "https://evil.example/rules", label: "Rules" }]
    }
  };
  const page = fakePage(start, pages);
  const result = await discoverGameInstructions(page);
  assert.deepEqual(result.visitedUrls, [start]);
  assert.equal(page.url(), start);
});

test("stops when a discovered instruction page is a verification gate", async () => {
  const start = "https://game.example/play";
  const pages = {
    "/play": { title: "Puzzle", text: "Play", links: [{ href: "/help", label: "Help" }] },
    "/help": { title: "Human verification", text: "Are you human? CAPTCHA required." }
  };
  const page = fakePage(start, pages);
  await assert.rejects(() => discoverGameInstructions(page), /Verification or anti-bot gate/);
});
