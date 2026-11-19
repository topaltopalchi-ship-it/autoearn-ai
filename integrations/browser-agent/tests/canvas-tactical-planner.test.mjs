import test from "node:test";
import assert from "node:assert/strict";
import { planCanvasTactics } from "../canvas-tactical-planner.mjs";

const player = { role: "player", x: 0.45, y: 0.45, width: 0.05, height: 0.05, confidence: 0.95 };
const target = { role: "target", x: 0.8, y: 0.45, width: 0.05, height: 0.05, confidence: 0.9 };
const hazard = (x, y) => ({ x, y, width: 0.08, height: 0.08, confidence: 0.95 });

test("pursues the nearest visible target when cardinal steps are clear", () => {
  const result = planCanvasTactics({ objects: [player, target], motion: { predictedHazards: [] } });
  assert.equal(result.mode, "pursue");
  assert.equal(result.suggestedKey, "ArrowRight");
  assert.equal(result.targetDetected, true);
});

test("evades a predicted hazard blocking the direct route to a target", () => {
  const result = planCanvasTactics({
    objects: [player, target],
    motion: { predictedHazards: [hazard(0.52, 0.44)] }
  });
  assert.equal(result.mode, "evade");
  assert.notEqual(result.suggestedKey, "ArrowRight");
});

test("waits when all four cardinal steps overlap predicted hazards", () => {
  const result = planCanvasTactics({
    objects: [player],
    motion: { predictedHazards: [
      hazard(0.45, 0.35), hazard(0.45, 0.55),
      hazard(0.35, 0.45), hazard(0.55, 0.45)
    ] }
  });
  assert.equal(result.mode, "wait");
  assert.equal(result.suggestedKey, null);
});

test("does not guess when player detection is missing or low confidence", () => {
  assert.equal(planCanvasTactics({ objects: [], motion: {} }).mode, "observe");
  assert.equal(planCanvasTactics({
    objects: [{ ...player, confidence: 0.4 }], motion: {}
  }).suggestedKey, null);
});

test("ignores low-confidence hazard detections and validates step size", () => {
  const result = planCanvasTactics({
    objects: [player, target],
    motion: { predictedHazards: [{ ...hazard(0.52, 0.44), confidence: 0.2 }] }
  });
  assert.equal(result.mode, "pursue");
  assert.throws(() => planCanvasTactics({ stepSize: 0.5 }), /stepSize/);
});


test("does not recommend a no-op direction when the player is at a canvas edge", () => {
  const edgePlayer = { ...player, x: 0.95, y: 0.45 };
  const edgeTarget = { ...target, x: 0.1, y: 0.45 };
  const result = planCanvasTactics({ objects: [edgePlayer, edgeTarget], motion: { predictedHazards: [] } });
  assert.notEqual(result.suggestedKey, "ArrowRight");
  assert.equal(result.suggestedKey, "ArrowLeft");
});
