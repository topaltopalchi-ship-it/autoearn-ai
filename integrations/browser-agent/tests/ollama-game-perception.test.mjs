import test from "node:test";
import assert from "node:assert/strict";
import { createOllamaGamePerception } from "../ollama-game-perception.mjs";

function mockFetch(content, capture = {}, status = 200) {
  return async (url, options) => {
    capture.url = url;
    capture.options = options;
    return { ok: status >= 200 && status < 300, status, json: async () => ({ message: { content } }) };
  };
}

const image = "data:image/png;base64,AAAA";

test("perceives a game screenshot using local Ollama and returns bounded structured state", async () => {
  const capture = {};
  const perceive = createOllamaGamePerception({
    model: "qwen2.5vl:3b",
    fetchImpl: mockFetch(JSON.stringify({
      scene: "game", confidence: 0.92, gameType: "platformer",
      objective: "Reach the exit", stateSummary: "Player near the left edge",
      visibleText: "Level 1", controls: ["Arrow keys", "Space"]
    }), capture)
  });
  const result = await perceive({ screenshot: image, title: "Game", text: "Level 1" });
  assert.equal(result.scene, "game");
  assert.equal(result.gameType, "platformer");
  assert.deepEqual(result.controls, ["Arrow keys", "Space"]);
  assert.equal(capture.url, "http://127.0.0.1:11434/api/chat");
  const body = JSON.parse(capture.options.body);
  assert.equal(body.model, "qwen2.5vl:3b");
  assert.deepEqual(body.messages[0].images, ["AAAA"]);
});

test("recognizes verification and unknown screens without converting them into game states", async () => {
  const verify = createOllamaGamePerception({
    model: "local-vlm",
    fetchImpl: mockFetch(JSON.stringify({ scene: "verification", confidence: 0.99 }))
  });
  assert.equal((await verify({ screenshot: image })).scene, "verification");
  const unknown = createOllamaGamePerception({
    model: "local-vlm",
    fetchImpl: mockFetch(JSON.stringify({ scene: "unknown", confidence: 0.2 }))
  });
  assert.equal((await unknown({ screenshot: image })).scene, "unknown");
});

test("rejects malformed confidence, invalid images, and remote endpoints", async () => {
  const bad = createOllamaGamePerception({
    model: "local-vlm",
    fetchImpl: mockFetch(JSON.stringify({ scene: "game", confidence: 2 }))
  });
  await assert.rejects(() => bad({ screenshot: image }), /confidence/);
  await assert.rejects(() => bad({ screenshot: "not-an-image" }), /Screenshot/);
  assert.throws(() => createOllamaGamePerception({
    model: "local-vlm", endpoint: "https://example.com"
  }), /loopback/);
});

test("enforces a local visual-perception call budget", async () => {
  const perceive = createOllamaGamePerception({
    model: "local-vlm", maxCalls: 1,
    fetchImpl: mockFetch(JSON.stringify({ scene: "game", confidence: 0.8 }))
  });
  await perceive({ screenshot: image });
  await assert.rejects(() => perceive({ screenshot: image }), /budget exhausted/);
});


test("returns only bounded visible object boxes with recognized roles", async () => {
  const perceive = createOllamaGamePerception({
    model: "local-vlm",
    fetchImpl: mockFetch(JSON.stringify({
      scene: "game", confidence: 0.91,
      objects: [
        { role: "player", label: "blue avatar", x: 0.1, y: 0.2, width: 0.1, height: 0.2, confidence: 0.95 },
        { role: "hazard", label: "spikes", x: 0.5, y: 0.7, width: 0.2, height: 0.1, confidence: 0.88 },
        { role: "target", x: 0.9, y: 0.1, width: 0.2, height: 0.2, confidence: 0.9 },
        { role: "unknown-role", x: 0.2, y: 0.2, width: 0.1, height: 0.1, confidence: 1 },
        { role: "goal", x: 0.2, y: 0.2, width: 0.1, height: 0.1, confidence: 1 }
      ]
    }))
  });
  const result = await perceive({ screenshot: image });
  assert.deepEqual(result.objects, [
    { role: "player", label: "blue avatar", x: 0.1, y: 0.2, width: 0.1, height: 0.2, confidence: 0.95 },
    { role: "hazard", label: "spikes", x: 0.5, y: 0.7, width: 0.2, height: 0.1, confidence: 0.88 },
    { role: "goal", label: "", x: 0.2, y: 0.2, width: 0.1, height: 0.1, confidence: 1 }
  ]);
});

test("limits object detections to thirty and rejects malformed boxes", async () => {
  const objects = Array.from({ length: 35 }, (_, i) => ({
    role: "target", x: i / 100, y: 0.2, width: 0.01, height: 0.1, confidence: 0.9
  }));
  const perceive = createOllamaGamePerception({
    model: "local-vlm",
    fetchImpl: mockFetch(JSON.stringify({ scene: "game", confidence: 0.9, objects }))
  });
  const result = await perceive({ screenshot: image });
  assert.equal(result.objects.length, 30);
  assert.equal(result.objects.every(item => item.x + item.width <= 1), true);
});
