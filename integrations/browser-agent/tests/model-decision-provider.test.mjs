import test from "node:test";
import assert from "node:assert/strict";
import { createOpenAIGameDecision } from "../model-decision-provider.mjs";

function mockFetch(payload, status = 200, capture = {}) {
  return async (url, options) => {
    capture.url = url;
    capture.options = options;
    return { ok: status >= 200 && status < 300, status, json: async () => payload };
  };
}

test("sends an observation and returns a validated keyboard action", async () => {
  const capture = {};
  const decide = createOpenAIGameDecision({
    apiKey: "test-key",
    model: "test-model",
    fetchImpl: mockFetch({ output_text: '{"type":"press","key":"ArrowLeft"}' }, 200, capture)
  });
  const action = await decide({ title: "Puzzle", snapshot: "Move tiles", screenshot: "data:image/png;base64,AAAA" });
  assert.deepEqual(action, { type: "press", key: "ArrowLeft" });
  assert.equal(capture.url, "https://api.openai.com/v1/responses");
  assert.equal(capture.options.headers.Authorization, "Bearer test-key");
  const body = JSON.parse(capture.options.body);
  assert.equal(body.model, "test-model");
  assert.equal(body.input[0].content[1].type, "input_image");
  assert.deepEqual(decide.usage, { calls: 1, maxCalls: 20, remaining: 19 });
});

test("stops when the model says no safe action is available", async () => {
  const decide = createOpenAIGameDecision({
    apiKey: "test-key", model: "test-model",
    fetchImpl: mockFetch({ output_text: '{"action":"stop"}' })
  });
  assert.equal(await decide({}), null);
});

test("rejects actions outside the configured key allowlist", async () => {
  const decide = createOpenAIGameDecision({
    apiKey: "test-key", model: "test-model",
    fetchImpl: mockFetch({ output_text: '{"type":"press","key":"KeyA"}' })
  });
  await assert.rejects(() => decide({}), /unsupported|allowlist/);
});

test("enforces a per-instance model-call budget", async () => {
  const decide = createOpenAIGameDecision({
    apiKey: "test-key", model: "test-model", maxCalls: 1,
    fetchImpl: mockFetch({ output_text: '{"type":"press","key":"Enter"}' })
  });
  assert.deepEqual(await decide({}), { type: "press", key: "Enter" });
  await assert.rejects(() => decide({}), /budget exhausted/);
});

test("requires an explicit API key and model", () => {
  assert.throws(() => createOpenAIGameDecision({ model: "x" }), /API key/);
  assert.throws(() => createOpenAIGameDecision({ apiKey: "x" }), /model/);
});
