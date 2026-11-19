import test from "node:test";
import assert from "node:assert/strict";
import { createOllamaGameDecision } from "../ollama-decision-provider.mjs";

function mockFetch(payload, status = 200, capture = {}) {
  return async (url, options) => {
    capture.url = url;
    capture.options = options;
    return { ok: status >= 200 && status < 300, status, json: async () => payload };
  };
}

test("sends observations to local Ollama and validates keyboard actions", async () => {
  const capture = {};
  const decide = createOllamaGameDecision({
    model: "qwen2.5vl:3b",
    fetchImpl: mockFetch({ message: { content: '{"type":"press","key":"ArrowRight"}' } }, 200, capture)
  });
  assert.deepEqual(await decide({ title: "Puzzle", snapshot: "Board state", screenshot: "data:image/png;base64,AAAA" }), {
    type: "press", key: "ArrowRight"
  });
  assert.equal(capture.url, "http://127.0.0.1:11434/api/chat");
  const body = JSON.parse(capture.options.body);
  assert.equal(body.model, "qwen2.5vl:3b");
  assert.equal(body.stream, false);
  assert.deepEqual(body.messages[0].images, ["AAAA"]);
});

test("stops when the local model requests stop", async () => {
  const decide = createOllamaGameDecision({
    model: "qwen2.5vl:3b",
    fetchImpl: mockFetch({ message: { content: '{"action":"stop"}' } })
  });
  assert.equal(await decide({}), null);
});

test("rejects unsupported keys and remote Ollama endpoints", async () => {
  const decide = createOllamaGameDecision({
    model: "local-model",
    fetchImpl: mockFetch({ message: { content: '{"type":"press","key":"KeyA"}' } })
  });
  await assert.rejects(() => decide({}), /allowlist/);
  assert.throws(() => createOllamaGameDecision({ model: "x", endpoint: "https://example.com" }), /loopback/);
});

test("enforces a local model call budget", async () => {
  const decide = createOllamaGameDecision({
    model: "local-model", maxCalls: 1,
    fetchImpl: mockFetch({ message: { content: '{"type":"press","key":"Enter"}' } })
  });
  assert.deepEqual(await decide({}), { type: "press", key: "Enter" });
  await assert.rejects(() => decide({}), /budget exhausted/);
});

test("requires a model name", () => {
  assert.throws(() => createOllamaGameDecision({}), /model name/);
});


test("includes only owner-rated experience hints for the observed state", async () => {
  let body;
  const decide = createOllamaGameDecision({
    model: "local-model",
    experienceMemory: {
      async getHints(input) {
        assert.deepEqual(input, {
          gameType: "2048",
          stateSummary: "two tiles",
          objective: "merge",
        });
        return [{ key: "ArrowLeft", good: 2, bad: 0, net: 2 }];
      }
    },
    fetchImpl: async (_url, options) => {
      body = JSON.parse(options.body);
      return { ok: true, status: 200, json: async () => ({
        message: { content: '{"type":"press","key":"ArrowLeft"}' }
      }) };
    }
  });
  await decide({
    gameState: { gameType: "2048", stateSummary: "two tiles", objective: "merge" }
  });
  assert.match(body.messages[0].content, /Owner-rated experience hints/);
  assert.match(body.messages[0].content, /ArrowLeft/);
});


test("accepts bounded indexed game-cell clicks and supplies targets to the local model", async () => {
  const capture = {};
  const decide = createOllamaGameDecision({
    model: "local-model", allowCellClicks: true,
    fetchImpl: mockFetch({ message: { content: '{"type":"click-cell","index":7}' } }, 200, capture)
  });
  assert.deepEqual(await decide({ clickTargets: [{ index: 7, label: "safe cell" }] }), { type: "click-cell", index: 7 });
  const body = JSON.parse(capture.options.body);
  assert.match(body.messages[0].content, /only for an index listed in clickTargets/);
  assert.match(body.messages[0].content, /safe cell/);
});

test("rejects game-cell clicks when disabled or outside the bounded index range", async () => {
  const disabled = createOllamaGameDecision({
    model: "local-model",
    fetchImpl: mockFetch({ message: { content: '{"type":"click-cell","index":1}' } })
  });
  await assert.rejects(() => disabled({}), /unsupported action/);
  const enabled = createOllamaGameDecision({
    model: "local-model", allowCellClicks: true,
    fetchImpl: mockFetch({ message: { content: '{"type":"click-cell","index":100}' } })
  });
  await assert.rejects(() => enabled({}), /unsupported action/);
});


test("accepts normalized canvas points only when canvas clicks are enabled and available", async () => {
  const decide = createOllamaGameDecision({
    model: "local-model", allowCanvasClicks: true,
    fetchImpl: mockFetch({ message: { content: '{"type":"click-canvas","x":0.25,"y":0.8,"confidence":0.93}' } })
  });
  assert.deepEqual(await decide({ canvasAvailable: true }), {
    type: "click-canvas", x: 0.25, y: 0.8, confidence: 0.93
  });
  await assert.rejects(() => decide({ canvasAvailable: false }), /canvas is available/);
});

test("rejects canvas clicks when disabled or outside normalized bounds", async () => {
  const disabled = createOllamaGameDecision({
    model: "local-model",
    fetchImpl: mockFetch({ message: { content: '{"type":"click-canvas","x":0.5,"y":0.5,"confidence":0.9}' } })
  });
  await assert.rejects(() => disabled({ canvasAvailable: true }), /unsupported action/);
  const enabled = createOllamaGameDecision({
    model: "local-model", allowCanvasClicks: true,
    fetchImpl: mockFetch({ message: { content: '{"type":"click-canvas","x":1.2,"y":0.5,"confidence":0.9}' } })
  });
  await assert.rejects(() => enabled({ canvasAvailable: true }), /unsupported action/);
});


test("requires at least 0.8 model confidence for canvas clicks", async () => {
  const low = createOllamaGameDecision({
    model: "local-model", allowCanvasClicks: true,
    fetchImpl: mockFetch({ message: { content: '{"type":"click-canvas","x":0.4,"y":0.6,"confidence":0.79}' } })
  });
  await assert.rejects(() => low({ canvasAvailable: true }), /unsupported action/);
  const missing = createOllamaGameDecision({
    model: "local-model", allowCanvasClicks: true,
    fetchImpl: mockFetch({ message: { content: '{"type":"click-canvas","x":0.4,"y":0.6}' } })
  });
  await assert.rejects(() => missing({ canvasAvailable: true }), /unsupported action/);
});


test("prefers the canvas-cropped decision image for coordinate selection", async () => {
  let body;
  const decide = createOllamaGameDecision({
    model: "local-model",
    allowCanvasClicks: true,
    fetchImpl: async (_url, options) => {
      body = JSON.parse(options.body);
      return { ok: true, status: 200, json: async () => ({
        message: { content: '{"type":"click-canvas","x":0.3,"y":0.7,"confidence":0.9}' }
      }) };
    }
  });
  await decide({
    canvasAvailable: true,
    screenshot: "data:image/png;base64,AAAA",
    decisionScreenshot: "data:image/jpeg;base64,BBBB"
  });
  assert.deepEqual(body.messages[0].images, ["BBBB"]);
});


test("falls back to the full screenshot when the canvas crop exceeds the image budget", async () => {
  let body;
  const decide = createOllamaGameDecision({
    model: "local-model",
    allowCanvasClicks: true,
    fetchImpl: async (_url, options) => {
      body = JSON.parse(options.body);
      return { ok: true, status: 200, json: async () => ({
        message: { content: '{"type":"click-canvas","x":0.3,"y":0.7,"confidence":0.9}' }
      }) };
    }
  });
  await decide({
    canvasAvailable: true,
    screenshot: "data:image/png;base64,AAAA",
    decisionScreenshot: "data:image/jpeg;base64," + "B".repeat(3_000_001)
  });
  assert.deepEqual(body.messages[0].images, ["AAAA"]);
});


test("explains that Canvas click JSON must include confidence", async () => {
  let prompt;
  const decide = createOllamaGameDecision({
    model: "local-model", allowCanvasClicks: true,
    fetchImpl: async (_url, options) => {
      prompt = JSON.parse(options.body).messages[0].content;
      return { ok: true, status: 200, json: async () => ({
        message: { content: '{"type":"press","key":"ArrowRight"}' }
      }) };
    }
  });
  await decide({ canvasAvailable: true });
  assert.match(prompt, /"confidence":0\.9/);
  assert.match(prompt, /at least 0\.8/);
});
