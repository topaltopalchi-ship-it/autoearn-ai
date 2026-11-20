import test from "node:test";
import assert from "node:assert/strict";
import { validateApprovedTarget } from "../approved-url.mjs";

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
