import test from "node:test";
import assert from "node:assert/strict";
import { normalizeDomGameMetrics, readDomGameMetrics } from "../dom-game-metrics.mjs";

test("normalizes only non-negative integer game metrics", () => {
  assert.deepEqual(normalizeDomGameMetrics({
    score: "120", level: "3", lives: "2", mistakes: "0", extra: "999"
  }), {
    gameState: {
      metrics: { score: 120, level: 3, lives: 2, mistakes: 0 },
      metricsSource: "dom-attribute"
    }
  });
});

test("rejects malformed, negative, fractional and oversized metric values", () => {
  assert.equal(normalizeDomGameMetrics({
    score: "-1", level: "1.5", lives: "999999999999999999999", mistakes: "NaN"
  }), null);
});

test("requires exactly one explicitly marked game board", async () => {
  const page = { locator() { return { async count() { return 2; } }; } };
  assert.equal(await readDomGameMetrics(page), null);
});

test("reads only explicit metric attributes from the unique game board", async () => {
  const page = {
    locator() {
      return {
        async count() { return 1; },
        async evaluate(fn) {
          return fn({
            getAttribute(name) {
              return ({
                "data-game-score": "25",
                "data-game-level": "2",
                "data-game-lives": "3",
                "data-game-mistakes": null
              })[name] ?? null;
            }
          });
        }
      };
    }
  };
  assert.deepEqual(await readDomGameMetrics(page), {
    gameState: {
      metrics: { score: 25, level: 2, lives: 3 },
      metricsSource: "dom-attribute"
    }
  });
});
