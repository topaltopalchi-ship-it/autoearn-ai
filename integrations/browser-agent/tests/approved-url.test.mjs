import test from "node:test";
import assert from "node:assert/strict";
import { validateApprovedTarget, isApprovedRequestUrl } from "../approved-url.mjs";

const origins = new Set(["https://games.example"]);

test("accepts only the exact approved HTTPS origin", () => {
  assert.equal(validateApprovedTarget("https://games.example/play", origins).href,
    "https://games.example/play");
});

test("rejects embedded credentials, nonstandard ports, and unapproved origins", () => {
  for (const url of [
    "https://user:secret@games.example/play",
    "https://games.example:8443/play",
    "https://other.example/play",
    "http://games.example/play"
  ]) {
    assert.throws(() => validateApprovedTarget(url, origins));
  }
});

test("blocks off-origin, insecure, credentialed, and nonstandard-port browser requests", () => {
  for (const url of [
    "http://games.example/script.js",
    "https://other.example/redirected",
    "https://user:secret@games.example/resource",
    "https://games.example:8443/resource",
    "not a URL"
  ]) {
    assert.equal(isApprovedRequestUrl(url, "https://games.example"), false, url);
  }
});

test("allows same-origin HTTPS resources", () => {
  assert.equal(isApprovedRequestUrl("https://games.example/assets/game.js", "https://games.example"), true);
});
