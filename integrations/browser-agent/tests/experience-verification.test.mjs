import test from "node:test";
import assert from "node:assert/strict";
import { hasMeaningfulStateChange, recordVerifiedExperience } from "../experience-verification.mjs";

test("records the exact allowlisted action only after a meaningful state change", async () => {
  const calls = [];
  const memory = { async recordPending(value) { calls.push(value); return "exp-1"; } };
  const pending = [];
  const before = {
    url: "https://game.example/play",
    snapshot: "score: 0",
    gameState: { gameType: "puzzle", stateSummary: "board A", objective: "score" },
    screenshot: "image-a"
  };
  const after = {
    ...before,
    snapshot: "score: 10",
    screenshot: "image-b"
  };
  assert.equal(await recordVerifiedExperience(memory, pending, {
    before, action: { type: "press", key: "ArrowRight" }, after
  }), true);
  assert.deepEqual(calls, [{
    gameType: "puzzle", stateSummary: "board A", objective: "score",
    action: { type: "press", key: "ArrowRight" }
  }]);
  assert.deepEqual(pending, [{ id: "exp-1", gameType: "puzzle", actionKey: "ArrowRight" }]);
});

test("does not treat screenshot animation alone as a verified state change", async () => {
  const before = { url: "https://game.example", snapshot: "same", screenshot: "frame-1" };
  const after = { ...before, screenshot: "frame-2" };
  let saved = false;
  assert.equal(hasMeaningfulStateChange(before, after), false);
  assert.equal(await recordVerifiedExperience({ async recordPending() { saved = true; } }, [], {
    before, action: { type: "press", key: "Enter" }, after
  }), false);
  assert.equal(saved, false);
});

test("does not save an experience when the state is unchanged", async () => {
  const state = { url: "https://game.example", snapshot: "unchanged" };
  let saved = false;
  assert.equal(await recordVerifiedExperience({ async recordPending() { saved = true; } }, [], {
    before: state, action: { type: "press", key: "Enter" }, after: { ...state }
  }), false);
  assert.equal(saved, false);
});

test("does not store non-keyboard actions while preserving successful state verification", async () => {
  const before = { snapshot: "before" };
  const after = { snapshot: "after" };
  let saved = false;
  assert.equal(await recordVerifiedExperience({ async recordPending() { saved = true; } }, [], {
    before, action: { type: "click", key: "ArrowRight" }, after
  }), true);
  assert.equal(saved, false);
});


test("records a verified indexed game-cell click for owner feedback", async () => {
  const calls = [];
  const memory = { async recordPending(value) { calls.push(value); return "cell-exp-1"; } };
  const pending = [];
  const before = { snapshot: "board before", gameState: { gameType: "memory", stateSummary: "two covered cards" } };
  const after = { snapshot: "board after", gameState: { gameType: "memory", stateSummary: "one revealed pair" } };
  assert.equal(await recordVerifiedExperience(memory, pending, {
    before, action: { type: "click-cell", index: 4 }, after
  }), true);
  assert.deepEqual(calls, [{ gameType: "memory", stateSummary: "two covered cards", objective: "", action: { type: "click-cell", index: 4 } }]);
  assert.deepEqual(pending, [{ id: "cell-exp-1", gameType: "memory", actionKey: "click-cell:4" }]);
});
