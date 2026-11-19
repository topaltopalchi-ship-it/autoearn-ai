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
