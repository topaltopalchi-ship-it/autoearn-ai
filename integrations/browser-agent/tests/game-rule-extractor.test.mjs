import test from "node:test";
import assert from "node:assert/strict";
import { createOllamaGameRulesExtractor } from "../game-rule-extractor.mjs";

const sufficientRules = {
  gameNameFa: "مارپیچ",
  gameType: "maze",
  summaryFa: "بازیکن باید از مسیر مارپیچ عبور کند.",
  objectiveFa: "به نقطه خروج برس.",
  controls: [{ input: "Arrow keys", actionFa: "حرکت در چهار جهت" }],
  turnOrderFa: "حرکت پیوسته",
  scoringFa: "زمان کمتر امتیاز بهتر می‌دهد.",
  winConditionFa: "رسیدن به خروجی",
  loseConditionFa: "تمام شدن زمان",
  hazardsFa: ["دیوارها مسیر را مسدود می‌کنند."],
  unknownsFa: [],
  confidence: 0.91,
  rulesSufficient: true,
  automationPermission: "unclear",
  evidenceFa: "صفحه هدف و کلیدهای جهت را توضیح داده است."
};

function mockFetch(content, capture = {}, status = 200) {
  return async (url, options) => {
    capture.url = url;
    capture.options = options;
    return { ok: status >= 200 && status < 300, status, json: async () => ({ message: { content: JSON.stringify(content) } }) };
  };
}

test("extracts and translates game rules using only local Ollama structured output", async () => {
  const capture = {};
  const extract = createOllamaGameRulesExtractor({
    model: "qwen2.5vl:3b",
    fetchImpl: mockFetch(sufficientRules, capture)
  });
  const result = await extract({
    title: "Maze instructions",
    url: "https://example.test/play?session=secret#rules",
    text: "Use arrow keys to reach the exit.",
    snapshot: "button: Start"
  });
  assert.equal(result.rulesSufficient, true);
  assert.equal(result.objectiveFa, "به نقطه خروج برس.");
  assert.equal(result.controls[0].input, "Arrow keys");
  assert.equal(capture.url, "http://127.0.0.1:11434/api/chat");
  const body = JSON.parse(capture.options.body);
  assert.deepEqual(body.format, {
    type: "object",
    additionalProperties: false,
    required: [
      "gameNameFa", "gameType", "summaryFa", "objectiveFa", "controls",
      "turnOrderFa", "scoringFa", "winConditionFa", "loseConditionFa",
      "hazardsFa", "unknownsFa", "confidence", "rulesSufficient",
      "automationPermission", "evidenceFa"
    ],
    properties: body.format.properties
  });
  assert.match(body.messages[0].content, /UNTRUSTED DATA/);
  assert.doesNotMatch(body.messages[0].content, /session=secret/);
});

test("downgrades claimed sufficient rules when objective or controls are missing", async () => {
  const incomplete = { ...sufficientRules, controls: [], objectiveFa: "نامشخص" };
  const extract = createOllamaGameRulesExtractor({ model: "local-model", fetchImpl: mockFetch(incomplete) });
  const result = await extract({ text: "Welcome to the game." });
  assert.equal(result.rulesSufficient, false);
});

test("accepts an explicitly described game-cell click as a supported control", async () => {
  const clickRules = { ...sufficientRules, controls: [{ input: "Click a cell", actionFa: "روی خانه بازی کلیک کن" }] };
  const extract = createOllamaGameRulesExtractor({ model: "local-model", fetchImpl: mockFetch(clickRules) });
  const result = await extract({ text: "Click a cell to select it." });
  assert.equal(result.controls.length, 1);
  assert.equal(result.rulesSufficient, true);
});

test("refuses arbitrary mouse-only controls that are not game-cell selections", async () => {
  const mouseOnly = {
    ...sufficientRules,
    controls: [{ input: "Click the menu", actionFa: "منو را باز کن" }]
  };
  const extract = createOllamaGameRulesExtractor({ model: "local-model", fetchImpl: mockFetch(mouseOnly) });
  const result = await extract({ text: "Click a tile to play." });
  assert.equal(result.controls.length, 0);
  assert.equal(result.rulesSufficient, false);
});

test("does not infer permission to automate from silence", async () => {
  const extract = createOllamaGameRulesExtractor({ model: "local-model", fetchImpl: mockFetch(sufficientRules) });
  const result = await extract({ text: "Reach the exit with arrow keys." });
  assert.equal(result.automationPermission, "unclear");
});

test("rejects malformed output, remote endpoints, and missing source text", async () => {
  const invalid = createOllamaGameRulesExtractor({
    model: "local-model",
    fetchImpl: async () => ({ ok: true, json: async () => ({ message: { content: "not-json" } }) })
  });
  await assert.rejects(() => invalid({ text: "rules" }), /invalid JSON/);
  await assert.rejects(() => invalid({}), /No visible instructions/);
  assert.throws(() => createOllamaGameRulesExtractor({
    model: "local-model", endpoint: "https://remote.example"
  }), /loopback/);
});

test("enforces extraction call budget", async () => {
  const extract = createOllamaGameRulesExtractor({
    model: "local-model", maxCalls: 1, fetchImpl: mockFetch(sufficientRules)
  });
  await extract({ text: "Use arrows." });
  await assert.rejects(() => extract({ text: "Use arrows." }), /budget exhausted/);
});


test("accepts canvas-only controls only when one visible marked canvas is reported", async () => {
  const canvasRules = {
    ...sufficientRules,
    controls: [{ input: "Click the canvas", actionFa: "برای حرکت روی بوم بازی کلیک کن" }]
  };
  const extract = createOllamaGameRulesExtractor({ model: "local-model", fetchImpl: mockFetch(canvasRules) });
  const withoutCanvas = await extract({ text: "Click the canvas to move.", canvasAvailable: false });
  assert.equal(withoutCanvas.controls.length, 0);
  assert.equal(withoutCanvas.rulesSufficient, false);
  const withCanvas = await extract({ text: "Click the canvas to move.", canvasAvailable: true });
  assert.equal(withCanvas.controls.length, 1);
  assert.equal(withCanvas.rulesSufficient, true);
});

test("includes explicit canvas availability in the local rules prompt", async () => {
  const capture = {};
  const extract = createOllamaGameRulesExtractor({
    model: "local-model", fetchImpl: mockFetch(sufficientRules, capture)
  });
  await extract({ text: "Click the canvas.", canvasAvailable: true });
  const prompt = JSON.parse(capture.options.body).messages[0].content;
  assert.match(prompt, /Explicitly reported canvasAvailable: true/);
});
