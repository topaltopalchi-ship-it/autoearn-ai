import test from "node:test";
import assert from "node:assert/strict";
import { detectGameOutcome, normalizeGameOutcome } from "../game-outcome-detector.mjs";

test("normalizes explicit win, loss and active states", () => {
  assert.equal(normalizeGameOutcome("VICTORY"), "won");
  assert.equal(normalizeGameOutcome("game_over"), "lost");
  assert.equal(normalizeGameOutcome("in progress"), "playing");
  assert.equal(normalizeGameOutcome("maybe"), "unknown");
});

test("prefers explicit DOM outcome attributes over generic visible text", () => {
  assert.deepEqual(detectGameOutcome({
    outcomeAttribute: "playing",
    bodyText: "You won a free bonus"
  }), { outcome: "playing", source: "dom-attribute" });
  assert.deepEqual(detectGameOutcome({ statusAttribute: "victory" }), {
    outcome: "won", source: "dom-attribute"
  });
});

test("recognizes only clear visible win/loss messages", () => {
  assert.equal(detectGameOutcome({ bodyText: "Congratulations, you won!" }).outcome, "won");
  assert.equal(detectGameOutcome({ bodyText: "You lost the game." }).outcome, "lost");
  assert.equal(detectGameOutcome({ bodyText: "Welcome to the game." }).outcome, "unknown");
});
