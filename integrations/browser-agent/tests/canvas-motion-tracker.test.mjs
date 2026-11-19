import test from "node:test";
import assert from "node:assert/strict";
import { createCanvasMotionTracker } from "../canvas-motion-tracker.mjs";

test("estimates short-horizon hazard motion from consecutive observations", () => {
  const tracker = createCanvasMotionTracker({ horizonMs: 500 });
  tracker.update([{ role: "hazard", label: "ball", x: 0.1, y: 0.2, width: 0.1, height: 0.1, confidence: 0.95 }], 1000);
  const result = tracker.update([
    { role: "hazard", label: "ball", x: 0.2, y: 0.2, width: 0.1, height: 0.1, confidence: 0.95 },
    { role: "target", label: "coin", x: 0.7, y: 0.4, width: 0.05, height: 0.05, confidence: 0.9 }
  ], 1500);
  assert.equal(result.horizonMs, 500);
  assert.equal(result.tracks[0].moving, true);
  assert.equal(result.tracks[0].velocityX, 0.2);
  assert.equal(result.predictedHazards.length, 1);
  assert.ok(Math.abs(result.predictedHazards[0].x - 0.3) < 1e-9);
});

test("does not extrapolate on first, stale, or ambiguous observations", () => {
  const tracker = createCanvasMotionTracker();
  const item = { role: "obstacle", label: "wall", x: 0.2, y: 0.2, width: 0.1, height: 0.1, confidence: 0.9 };
  const first = tracker.update([item], 1000);
  assert.equal(first.horizonMs, 0);
  const stale = tracker.update([{ ...item, x: 0.4 }], 5000);
  assert.equal(stale.horizonMs, 0);
  assert.equal(stale.predictedHazards[0].x, 0.4);
});

test("rejects invalid detections and bounds output", () => {
  const tracker = createCanvasMotionTracker();
  const result = tracker.update([
    { role: "hazard", x: 0.9, y: 0.9, width: 0.2, height: 0.2, confidence: 1 },
    ...Array.from({ length: 40 }, (_, i) => ({
      role: "target", x: i / 100, y: 0.2, width: 0.01, height: 0.01, confidence: 0.9
    }))
  ], 1);
  assert.equal(result.tracks.length, 30);
});
