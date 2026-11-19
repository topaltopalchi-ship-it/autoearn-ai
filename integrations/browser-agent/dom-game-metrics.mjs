const METRICS = ["score", "level", "lives", "mistakes"];

export function normalizeDomGameMetrics(raw) {
  if (!raw || typeof raw !== "object") return null;
  const metrics = {};
  for (const key of METRICS) {
    const value = raw[key];
    if (value === null || value === undefined || value === "") continue;
    const number = typeof value === "number" ? value :
      typeof value === "string" && /^\d{1,12}$/.test(value.trim()) ? Number(value) : NaN;
    if (Number.isSafeInteger(number) && number >= 0) metrics[key] = number;
  }
  return Object.keys(metrics).length ? { gameState: { metrics, metricsSource: "dom-attribute" } } : null;
}

/** Reads only explicit data-game-* attributes from exactly one marked game board. */
export async function readDomGameMetrics(page) {
  if (!page || typeof page.locator !== "function") throw new TypeError("A Playwright Page is required.");
  const board = page.locator("[data-game-board]");
  if (await board.count() !== 1) return null;
  const raw = await board.evaluate(element => ({
    score: element.getAttribute("data-game-score"),
    level: element.getAttribute("data-game-level"),
    lives: element.getAttribute("data-game-lives"),
    mistakes: element.getAttribute("data-game-mistakes")
  }));
  return normalizeDomGameMetrics(raw);
}
