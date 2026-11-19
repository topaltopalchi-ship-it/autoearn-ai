import test from "node:test";
import assert from "node:assert/strict";
import { isSafeNavigationTarget } from "../site-navigation.mjs";

const origin = "https://games.example";

test("allows same-origin HTTPS folder links", () => {
  assert.equal(isSafeNavigationTarget({ role: "link", name: "Puzzle room", href: origin + "/rooms/puzzle" }, origin), true);
});

test("blocks external, insecure, and sensitive destinations", () => {
  assert.equal(isSafeNavigationTarget({ role: "link", name: "Game", href: "https://other.example/game" }, origin), false);
  assert.equal(isSafeNavigationTarget({ role: "link", name: "Game", href: "http://games.example/game" }, origin), false);
  assert.equal(isSafeNavigationTarget({ role: "link", name: "Claim prize", href: origin + "/claim" }, origin), false);
  assert.equal(isSafeNavigationTarget({ role: "button", name: "Submit payment" }, origin), false);
});

test("allows non-sensitive buttons that may expand folders", () => {
  assert.equal(isSafeNavigationTarget({ role: "button", name: "Arcade games" }, origin), true);
});
