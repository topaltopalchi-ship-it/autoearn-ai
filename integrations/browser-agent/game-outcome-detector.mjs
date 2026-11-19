const WIN = new Set(["win", "won", "victory", "success", "completed", "complete", "winner"]);
const LOSS = new Set(["loss", "lost", "defeat", "failed", "failure", "game_over", "game-over"]);
const ACTIVE = new Set(["playing", "active", "in_progress", "in-progress", "running"]);

function normalize(value) {
  return String(value || "").trim().toLowerCase().replace(/\s+/g, "_");
}

export function normalizeGameOutcome(value) {
  const key = normalize(value);
  if (WIN.has(key)) return "won";
  if (LOSS.has(key)) return "lost";
  if (ACTIVE.has(key)) return "playing";
  return "unknown";
}

/** Explicit DOM outcome attributes take priority over conservative visible-text hints. */
export function detectGameOutcome({ outcomeAttribute = "", statusAttribute = "", bodyText = "" } = {}) {
  for (const value of [outcomeAttribute, statusAttribute]) {
    const normalized = normalizeGameOutcome(value);
    if (normalized !== "unknown") return { outcome: normalized, source: "dom-attribute" };
  }
  const text = String(bodyText || "");
  if (/\b(you win|you won|victory|level completed|puzzle completed)\b|برنده شدی|پیروز شدی|مرحله را بردی/i.test(text)) {
    return { outcome: "won", source: "visible-text" };
  }
  if (/\b(you lose|you lost|defeat|game over|you failed)\b|باختی|شکست خوردی|بازی تمام شد/i.test(text)) {
    return { outcome: "lost", source: "visible-text" };
  }
  return { outcome: "unknown", source: "none" };
}
