import test from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, rm } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { createGameExperienceMemory, createStateKey } from "../game-experience-memory.mjs";

async function withMemory(run) {
  const dir = await mkdtemp(join(tmpdir(), "autoearn-memory-"));
  try {
    const memory = createGameExperienceMemory({ filePath: join(dir, "memory.json") });
    await run(memory);
  } finally {
    await rm(dir, { recursive: true, force: true });
  }
}

test("stores only a hashed state and allowlisted action, then reloads evidence-backed hints", async () => {
  await withMemory(async memory => {
    const input = {
      gameType: "2048",
      stateSummary: "Tiles at positions 0 and 1",
      objective: "Combine equal tiles",
      action: { type: "press", key: "ArrowLeft" }
    };
    const firstId = await memory.recordPending(input);
    assert.match(firstId, /^[0-9a-f-]{36}$/);
    assert.deepEqual(await memory.pending(), [{
      id: firstId, gameType: "2048", actionKey: "ArrowLeft",
      createdAt: (await memory.pending())[0].createdAt
    }]);
    await memory.rate(firstId, "good");
    assert.deepEqual(await memory.getHints(input), []);
    const secondId = await memory.recordPending(input);
    await memory.rate(secondId, "good");
    assert.deepEqual(await memory.getHints(input), [
      { key: "ArrowLeft", good: 2, bad: 0, net: 2, sampleCount: 2, successRate: 0.75 }
    ]);
  });
});

test("keeps pending and single-rating feedback out of hints; rejects repeat ratings", async () => {
  await withMemory(async memory => {
    const input = { gameType: "platformer", stateSummary: "At start", action: { type: "press", key: " " } };
    const id = await memory.recordPending(input);
    assert.deepEqual(await memory.getHints(input), []);
    await memory.rate(id, "bad");
    assert.deepEqual(await memory.getHints(input), []);
    const secondId = await memory.recordPending(input);
    await memory.rate(secondId, "bad");
    await assert.rejects(() => memory.rate(id, "good"), /already been rated/);
    assert.deepEqual(await memory.getHints(input), [
      { key: " ", good: 0, bad: 2, net: -2, sampleCount: 2, successRate: 0.25 }
    ]);
  });
});

test("smooths conflicting evidence and ranks it below consistently positive evidence", async () => {
  await withMemory(async memory => {
    const input = { gameType: "puzzle", stateSummary: "same board" };
    for (const feedback of ["good", "bad"]) {
      const id = await memory.recordPending({ ...input, action: { type: "press", key: "ArrowLeft" } });
      await memory.rate(id, feedback);
    }
    for (const feedback of ["good", "good", "good"]) {
      const id = await memory.recordPending({ ...input, action: { type: "press", key: "ArrowRight" } });
      await memory.rate(id, feedback);
    }
    const hints = await memory.getHints(input);
    assert.equal(hints[0].key, "ArrowRight");
    assert.equal(hints[0].successRate, 0.8);
    assert.equal(hints[1].key, "ArrowLeft");
    assert.equal(hints[1].successRate, 0.5);
  });
});

test("isolates state contexts and rejects unsupported actions or feedback", async () => {
  await withMemory(async memory => {
    const id = await memory.recordPending({
      gameType: "2048", stateSummary: "State A", action: { type: "press", key: "ArrowRight" }
    });
    await memory.rate(id, "good");
    assert.deepEqual(await memory.getHints({ gameType: "2048", stateSummary: "State B" }), []);
    await assert.rejects(() => memory.recordPending({
      gameType: "2048", action: { type: "click", key: "ArrowRight" }
    }), /allowlisted/);
    await assert.rejects(() => memory.rate(id, "neutral"), /good or bad/);
  });
});

test("state keys are stable and do not expose source text", () => {
  const a = createStateKey({ gameType: "2048", stateSummary: "private board text" });
  const b = createStateKey({ gameType: "2048", stateSummary: "private board text" });
  assert.equal(a, b);
  assert.match(a, /^[a-f0-9]{64}$/);
  assert.equal(a.includes("private"), false);
});

test("stores and rates bounded indexed cell-click experiences", async () => {
  await withMemory(async memory => {
    const input = { gameType: "memory", stateSummary: "two covered cards", action: { type: "click-cell", index: 4 } };
    for (let i = 0; i < 2; i++) {
      const id = await memory.recordPending(input);
      await memory.rate(id, "good");
    }
    assert.deepEqual(await memory.getHints(input), [
      { key: "click-cell:4", good: 2, bad: 0, net: 2, sampleCount: 2, successRate: 0.75 }
    ]);
    await assert.rejects(() => memory.recordPending({ ...input, action: { type: "click-cell", index: 100 } }), /allowlisted/);
  });
});

test("stores confident canvas clicks as coarse regions without retaining raw coordinates", async () => {
  await withMemory(async memory => {
    const input = {
      gameType: "canvas-puzzle",
      stateSummary: "target near upper left",
      objective: "hit the target",
      action: { type: "click-canvas", x: 0.14, y: 0.28, confidence: 0.91 }
    };
    for (let i = 0; i < 2; i++) {
      const id = await memory.recordPending(input);
      await memory.rate(id, "good");
    }
    assert.deepEqual(await memory.getHints(input), [
      { key: "click-canvas:1:2", good: 2, bad: 0, net: 2, sampleCount: 2, successRate: 0.75 }
    ]);
    await assert.rejects(() => memory.recordPending({
      ...input, action: { ...input.action, confidence: 0.79 }
    }), /confidence/);
    await assert.rejects(() => memory.recordPending({
      ...input, action: { ...input.action, x: 1.2 }
    }), /confidence/);
  });
});

test("expires stale rated experiences so old strategies do not bias new sessions", async () => {
  const dir = await mkdtemp(join(tmpdir(), "autoearn-memory-expiry-"));
  const filePath = join(dir, "memory.json");
  try {
    const oldMemory = createGameExperienceMemory({
      filePath,
      now: () => "2026-01-01T00:00:00.000Z"
    });
    const input = { gameType: "runner", stateSummary: "same obstacle", action: { type: "press", key: "ArrowUp" } };
    const id = await oldMemory.recordPending(input);
    await oldMemory.rate(id, "good");
    const freshMemory = createGameExperienceMemory({
      filePath,
      now: () => "2026-02-15T00:00:00.000Z"
    });
    assert.deepEqual(await freshMemory.getHints(input), []);
    assert.deepEqual(await freshMemory.pending(), []);
  } finally {
    await rm(dir, { recursive: true, force: true });
  }
});
