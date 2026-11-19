import test from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, rm } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { clickSafeGameCanvas } from "../game-cell-browser-adapter.mjs";
import { createGameExperienceMemory } from "../game-experience-memory.mjs";
import { recordVerifiedExperience } from "../experience-verification.mjs";

// Deterministic local fixture: a target occupies the center-left quarter of a
// marked 200x100 canvas. The fake Playwright surface preserves the real adapter
// geometry contract while keeping this integration test browser-binary-free.
function createCanvasFixture() {
  const state = { score: 0, summary: "target-awaiting-click" };
  const canvas = {
    count: async () => 1,
    evaluate: async () => true,
    boundingBox: async () => ({ x: 0, y: 0, width: 200, height: 100 }),
    click: async ({ position }) => {
      const nx = position.x / 200;
      const ny = position.y / 100;
      if (nx >= 0.15 && nx <= 0.35 && ny >= 0.35 && ny <= 0.65) {
        state.score += 1;
        state.summary = "target-hit-score-1";
      }
    }
  };
  return {
    page: { locator: selector => {
      assert.equal(selector, '[data-game-board] canvas[data-game-canvas]');
      return canvas;
    }},
    state
  };
}

test("canvas agent click changes a synthetic game and stores a rateable verified experience", async () => {
  const directory = await mkdtemp(join(tmpdir(), "autoearn-canvas-fixture-"));
  try {
    const memory = createGameExperienceMemory({ filePath: join(directory, "memory.json") });
    const pending = [];
    const { page, state } = createCanvasFixture();
    const before = {
      url: "https://fixture.invalid/game",
      snapshot: "score:0",
      gameState: {
        gameType: "canvas-target",
        stateSummary: state.summary,
        objective: "click the visible target"
      }
    };

    const action = { type: "click-canvas", x: 0.25, y: 0.5, confidence: 0.95 };
    await clickSafeGameCanvas(page, action.x, action.y, action.confidence);
    assert.equal(state.score, 1);
    assert.equal(state.summary, "target-hit-score-1");

    const after = {
      ...before,
      snapshot: "score:1",
      gameState: { ...before.gameState, stateSummary: state.summary }
    };
    assert.equal(await recordVerifiedExperience(memory, pending, { before, action, after }), true);
    assert.equal(pending.length, 1);
    assert.equal(pending[0].actionKey, "click-canvas:2:5");

    await memory.rate(pending[0].id, "good");
    assert.deepEqual(await memory.getHints({
      gameType: "canvas-target",
      stateSummary: "target-awaiting-click",
      objective: "click the visible target"
    }), [{ key: "click-canvas:2:5", good: 1, bad: 0, net: 1 }]);
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
});
