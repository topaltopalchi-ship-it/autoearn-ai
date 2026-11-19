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
