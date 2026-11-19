import test from "node:test";
import assert from "node:assert/strict";
import { evaluateGameProgress } from "../game-progress-evaluator.mjs";

const box = (role, x, y, confidence = 0.95) => ({
  role, x, y, width: 0.05, height: 0.05, confidence
});

test("rewards verified movement closer to a visible target", () => {
  const before = { canvasObjects: [box("player", 0.1, 0.2), box("target", 0.8, 0.2)] };
  const after = { canvasObjects: [box("player", 0.4, 0.2), box("target", 0.8, 0.2)] };
  assert.deepEqual(evaluateGameProgress(before, after), {
    reward: 1, feedback: "good", confidence: 0.75, signals: ["closer-to-target"]
  });
});

test("penalizes movement farther from a target", () => {
  const before = { canvasObjects: [box("player", 0.4, 0.2), box("target", 0.8, 0.2)] };
  const after = { canvasObjects: [box("player", 0.1, 0.2), box("target", 0.8, 0.2)] };
  assert.equal(evaluateGameProgress(before, after).feedback, "bad");
});

test("uses explicit win and loss markers as strongest signals", () => {
  const before = { gameState: { outcome: "playing", outcomeSource: "dom-attribute" } };
  assert.equal(evaluateGameProgress(before, {
    gameState: { outcome: "won", outcomeSource: "dom-attribute" }
  }).reward, 3);
  assert.equal(evaluateGameProgress(before, {
    gameState: { outcome: "lost", outcomeSource: "dom-attribute" }
  }).reward, -3);
});

test("visible-text outcome hints never receive automatic-rating confidence", () => {
  const before = { gameState: { outcome: "playing", outcomeSource: "none" } };
  const result = evaluateGameProgress(before, {
    gameState: { outcome: "won", outcomeSource: "visible-text" }
  });
  assert.equal(result.feedback, "good");
  assert.equal(result.confidence, 0.75);
  assert.deepEqual(result.signals, ["visible-win-hint"]);
});

test("rewards moving clear of a predicted hazard and penalizes overlap", () => {
  const hazard = { x: 0.3, y: 0.3, width: 0.1, height: 0.1, confidence: 0.95 };
  const before = {
    canvasObjects: [box("player", 0.3, 0.3)],
    canvasMotion: { predictedHazards: [hazard] }
  };
  const after = {
    canvasObjects: [box("player", 0.6, 0.6)],
    canvasMotion: { predictedHazards: [] }
  };
  assert.ok(evaluateGameProgress(before, after).signals.includes("moved-away-from-hazard"));
  assert.ok(evaluateGameProgress({ canvasObjects: [box("player", 0.1, 0.1)] }, {
    canvasObjects: [box("player", 0.3, 0.3)],
    canvasMotion: { predictedHazards: [hazard] }
  }).signals.includes("predicted-hazard-overlap"));
});

test("returns neutral when evidence is missing or confidence is low", () => {
  const result = evaluateGameProgress({}, { canvasObjects: [box("player", 0.2, 0.2, 0.3)] });
  assert.equal(result.feedback, "neutral");
  assert.equal(result.confidence, 0);
});

test("uses only DOM-sourced score, level, lives and mistake metrics", () => {
  const before = { gameState: {
    metricsSource: "dom-attribute",
    metrics: { score: 10, level: 1, lives: 3, mistakes: 2 }
  }};
  const after = { gameState: {
    metricsSource: "dom-attribute",
    metrics: { score: 20, level: 2, lives: 2, mistakes: 1 }
  }};
  const result = evaluateGameProgress(before, after);
  assert.equal(result.reward, 4);
  assert.equal(result.feedback, "good");
  assert.deepEqual(result.signals, ["score-increased", "level-increased", "lives-decreased", "mistakes-decreased"]);
});

test("ignores numeric metrics without explicit DOM provenance", () => {
  const before = { gameState: { metrics: { score: 10 } } };
  const after = { gameState: { metrics: { score: 999 } } };
  const result = evaluateGameProgress(before, after);
  assert.equal(result.reward, 0);
  assert.equal(result.confidence, 0);
  assert.deepEqual(result.signals, []);
});

test("ignores missing and non-numeric metric values", () => {
  const before = { gameState: { metricsSource: "dom-attribute", metrics: { score: 10, level: 1 } } };
  const after = { gameState: { metricsSource: "dom-attribute", metrics: { score: "999", level: 1 } } };
  const result = evaluateGameProgress(before, after);
  assert.equal(result.reward, 0);
  assert.deepEqual(result.signals, []);
});


test("trusted terminal outcomes take precedence over contradictory weaker signals", () => {
  const before = {
    gameState: {
      outcome: "playing", outcomeSource: "dom-attribute",
      metricsSource: "dom-attribute", metrics: { score: 100, lives: 5, mistakes: 0 }
    },
    canvasObjects: [box("player", 0.1, 0.1), box("target", 0.8, 0.8)]
  };
  const won = evaluateGameProgress(before, {
    gameState: {
      outcome: "won", outcomeSource: "dom-attribute",
      metricsSource: "dom-attribute", metrics: { score: 0, lives: 0, mistakes: 99 }
    },
    canvasObjects: [box("player", 0.1, 0.1), box("target", 0.8, 0.8)],
    canvasMotion: { predictedHazards: [{ x: 0.1, y: 0.1, width: 0.1, height: 0.1, confidence: 0.99 }] }
  });
  assert.deepEqual(won, { reward: 3, feedback: "good", confidence: 1, signals: ["explicit-win"] });

  const lost = evaluateGameProgress(before, {
    gameState: { outcome: "lost", outcomeSource: "dom-attribute" },
    canvasObjects: [box("player", 0.1, 0.1), box("target", 0.8, 0.8)]
  });
  assert.deepEqual(lost, { reward: -3, feedback: "bad", confidence: 1, signals: ["explicit-loss"] });
});
