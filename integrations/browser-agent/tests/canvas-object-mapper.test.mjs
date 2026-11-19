import test from "node:test";
import assert from "node:assert/strict";
import { mapViewportObjectsToCanvas } from "../canvas-object-mapper.mjs";

test("maps full viewport detections into normalized Canvas coordinates", () => {
  const result = mapViewportObjectsToCanvas([
    { role: "player", label: "avatar", x: 0.3, y: 0.3, width: 0.1, height: 0.2, confidence: 0.9 },
    { role: "hazard", label: "partly outside", x: 0.45, y: 0.4, width: 0.2, height: 0.2, confidence: 0.8 },
    { role: "other", label: "outside", x: 0.9, y: 0.9, width: 0.05, height: 0.05, confidence: 0.9 }
  ], { x: 200, y: 100, width: 400, height: 200 }, { width: 800, height: 400 });
  assert.deepEqual(result, [
    { role: "player", label: "avatar", x: 0.2, y: 0.1, width: 0.2, height: 0.4, confidence: 0.9 },
    { role: "hazard", label: "partly outside", x: 0.5, y: 0.3, width: 0.5, height: 0.4, confidence: 0.8 }
  ]);
});

test("rejects invalid geometry and clips boxes that do not intersect the Canvas", () => {
  assert.deepEqual(mapViewportObjectsToCanvas([
    { role: "target", x: 0.1, y: 0.1, width: 0.1, height: 0.1, confidence: 0.9 },
    { role: "target", x: 0.9, y: 0.9, width: 0.2, height: 0.2, confidence: 0.9 }
  ], { x: 200, y: 100, width: 400, height: 200 }, { width: 800, height: 400 }), []);
  assert.deepEqual(mapViewportObjectsToCanvas([], { x: 0, y: 0, width: 0, height: 1 }, { width: 1, height: 1 }), []);
});
