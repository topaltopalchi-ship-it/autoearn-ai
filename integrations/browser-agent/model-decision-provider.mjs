const DEFAULT_KEYS = new Set(["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "Enter", "Escape", " "]);

function extractOutputText(response) {
  if (typeof response?.output_text === "string") return response.output_text;
  const chunks = [];
  for (const item of response?.output ?? []) {
    if (item?.type !== "message") continue;
    for (const part of item.content ?? []) {
      if (part?.type === "output_text" && typeof part.text === "string") chunks.push(part.text);
    }
  }
  return chunks.join("\n");
}

function parseAction(text) {
  let parsed;
  try {
    const cleaned = text.trim().replace(/^\x60{3}(?:json)?\s*/i, "").replace(/\s*\x60{3}$/i, "");
    parsed = JSON.parse(cleaned);
  } catch {
    throw new Error("The model returned an invalid action payload.");
  }
  if (parsed === null || parsed.action === "stop") return null;
  if (parsed.type !== "press" || typeof parsed.key !== "string") {
    throw new Error("The model requested an unsupported game action.");
  }
  return { type: "press", key: parsed.key };
}

/**
 * Creates a bounded OpenAI Responses API decision function.
 * Keep the API key in a trusted server/worker environment, never in browser code.
 */
export function createOpenAIGameDecision({
  apiKey,
  model,
  maxCalls = 20,
  timeoutMs = 15_000,
  allowedKeys = DEFAULT_KEYS,
  fetchImpl = globalThis.fetch
} = {}) {
  if (typeof apiKey !== "string" || !apiKey.trim()) throw new TypeError("An OpenAI API key is required.");
  if (typeof model !== "string" || !model.trim()) throw new TypeError("An explicit model name is required.");
  if (!Number.isInteger(maxCalls) || maxCalls < 1 || maxCalls > 500) throw new RangeError("maxCalls must be from 1 to 500.");
  if (!Number.isInteger(timeoutMs) || timeoutMs < 1_000 || timeoutMs > 60_000) throw new RangeError("timeoutMs must be from 1000 to 60000.");
  if (typeof fetchImpl !== "function") throw new TypeError("A fetch implementation is required.");
  const keys = new Set(allowedKeys);
  if (!keys.size || [...keys].some(key => !DEFAULT_KEYS.has(key))) {
    throw new TypeError("allowedKeys may contain only supported keyboard keys.");
  }
  let calls = 0;

  const decide = async observation => {
    if (calls >= maxCalls) throw new Error("Model decision call budget exhausted.");
    if (!observation || typeof observation !== "object") throw new TypeError("A game observation is required.");
    const snapshot = {
      title: String(observation.title ?? "").slice(0, 160),
      url: String(observation.url ?? "").slice(0, 500),
      text: String(observation.snapshot ?? observation.text ?? "").slice(0, 6_000),
      gameState: observation.gameState ?? observation.state ?? null
    };
    const content = [{
      type: "input_text",
      text: [
        "You are a cautious game decision module. Analyze only the supplied game observation.",
        "Return exactly one JSON object: {\"type\":\"press\",\"key\":\"ArrowUp\"} or {\"action\":\"stop\"}.",
        "Never request clicks, navigation, typing, purchases, account actions, or bypasses.",
        "Choose only one of these allowed keys: " + [...keys].join(", "),
        "If the game is unclear, blocked, asks for CAPTCHA/verification, or no safe move is evident, return {\"action\":\"stop\"}.",
        "Observation JSON: " + JSON.stringify(snapshot)
      ].join("\n")
    }];
    if (typeof observation.screenshot === "string" && /^data:image\/(png|jpeg|webp);base64,/.test(observation.screenshot)) {
      content.push({ type: "input_image", image_url: observation.screenshot });
    }
    calls++;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const response = await fetchImpl("https://api.openai.com/v1/responses", {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${apiKey}`,
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ model, input: [{ role: "user", content }] }),
        signal: controller.signal
      });
      if (!response.ok) throw new Error(`OpenAI Responses API request failed (HTTP ${response.status}).`);
      const payload = await response.json();
      if (payload?.status && payload.status !== "completed") throw new Error("The model response did not complete.");
      const action = parseAction(extractOutputText(payload));
      if (action && !keys.has(action.key)) throw new Error("The model selected a key outside the configured allowlist.");
      return action;
    } finally {
      clearTimeout(timeout);
    }
  };
  Object.defineProperty(decide, "usage", { get: () => ({ calls, maxCalls, remaining: maxCalls - calls }) });
  return decide;
}
