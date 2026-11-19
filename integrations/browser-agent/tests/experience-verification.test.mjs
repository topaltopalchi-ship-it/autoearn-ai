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
  assert.deepEqual(pending, [{
    id: "exp-1", gameType: "puzzle", actionKey: "ArrowRight",
    progress: { reward: 0, feedback: "neutral", confidence: 0, signals: [] },
    feedbackStatus: "needs-review"
  }]);
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
  assert.deepEqual(pending, [{
    id: "cell-exp-1", gameType: "memory", actionKey: "click-cell:4",
    progress: { reward: 0, feedback: "neutral", confidence: 0, signals: [] },
    feedbackStatus: "needs-review"
  }]);
});


test("records a confident canvas click only after a meaningful game-state change", async () => {
  const calls = [];
  const memory = { async recordPending(value) { calls.push(value); return "canvas-exp-1"; } };
  const pending = [];
  const before = { snapshot: "target at left", gameState: { gameType: "canvas-puzzle", stateSummary: "target-left", objective: "hit target" } };
  const after = { snapshot: "target moved", gameState: { gameType: "canvas-puzzle", stateSummary: "target-moved", objective: "hit target" } };
  const action = { type: "click-canvas", x: 0.14, y: 0.28, confidence: 0.93 };
  assert.equal(await recordVerifiedExperience(memory, pending, { before, action, after }), true);
  assert.deepEqual(calls, [{
    gameType: "canvas-puzzle", stateSummary: "target-left", objective: "hit target", action
  }]);
  assert.deepEqual(pending, [{
    id: "canvas-exp-1", gameType: "canvas-puzzle", actionKey: "click-canvas:1:2",
    progress: { reward: 0, feedback: "neutral", confidence: 0, signals: [] },
    feedbackStatus: "needs-review"
  }]);
});

test("does not remember low-confidence canvas clicks", async () => {
  let saved = false;
  const before = { snapshot: "before" };
  const after = { snapshot: "after" };
  assert.equal(await recordVerifiedExperience({ async recordPending() { saved = true; } }, [], {
    before, after, action: { type: "click-canvas", x: 0.4, y: 0.6, confidence: 0.79 }
  }), true);
  assert.equal(saved, false);
});


test("automatically rates only explicit terminal win or loss outcomes", async () => {
  const rated = [];
  const memory = {
    async recordPending() { return "terminal-exp"; },
    async rate(id, feedback) { rated.push({ id, feedback }); }
  };
  const pending = [];
  const before = { snapshot: "playing", gameState: { gameType: "puzzle", outcome: "playing", outcomeSource: "dom-attribute" } };
  const after = { snapshot: "finished", gameState: { gameType: "puzzle", outcome: "won", outcomeSource: "dom-attribute" } };
  await recordVerifiedExperience(memory, pending, {
    before, after, action: { type: "press", key: "ArrowRight" }
  });
  assert.deepEqual(rated, [{ id: "terminal-exp", feedback: "good" }]);
  assert.equal(pending[0].feedbackStatus, "auto-rated-explicit-outcome");
});


test("recognizes meaningful Canvas object movement without relying on screenshot animation", () => {
  const before = {
    snapshot: "same visible text",
    canvasObjects: [{ role: "player", label: "hero", x: 0.1, y: 0.2, width: 0.1, height: 0.1, confidence: 0.95 }]
  };
  const after = {
    snapshot: "same visible text",
    canvasObjects: [{ role: "player", label: "hero", x: 0.15, y: 0.2, width: 0.1, height: 0.1, confidence: 0.95 }]
  };
  assert.equal(hasMeaningfulStateChange(before, after), true);
});

test("ignores tiny or low-confidence Canvas detection jitter", () => {
  const before = {
    snapshot: "same",
    canvasObjects: [{ role: "player", label: "hero", x: 0.1, y: 0.2, width: 0.1, height: 0.1, confidence: 0.95 }]
  };
  const after = {
    snapshot: "same",
    canvasObjects: [{ role: "player", label: "hero", x: 0.105, y: 0.2, width: 0.1, height: 0.1, confidence: 0.5 }]
  };
  assert.equal(hasMeaningfulStateChange(before, after), false);
});

test("does not remember arbitrary keyboard keys or retain extra action properties", async () => {
  const calls = [];
  const memory = { async recordPending(value) { calls.push(value); return "safe-exp"; } };
  const before = { snapshot: "before" };
  const after = { snapshot: "after" };
  await recordVerifiedExperience(memory, [], {
    before, after, action: { type: "press", key: "Control+V", pastedSecret: "must-not-be-stored" }
  });
  assert.equal(calls.length, 0);
  await recordVerifiedExperience(memory, [], {
    before, after, action: { type: "press", key: "ArrowLeft", pastedSecret: "must-not-be-stored" }
  });
  assert.deepEqual(calls, [{
    gameType: "unknown", stateSummary: "", objective: "",
    action: { type: "press", key: "ArrowLeft" }
  }]);
});
