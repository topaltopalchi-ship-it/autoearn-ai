import { createHash, randomUUID } from "node:crypto";
import { mkdir, readFile, rename, writeFile } from "node:fs/promises";
import { dirname } from "node:path";

const VERSION = 1;
const MAX_RECORDS = 1000;
const ACTION_KEYS = new Set(["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "Enter", "Escape", " "]);

export function createStateKey({ gameType = "unknown", stateSummary = "", objective = "" } = {}) {
  const safeType = String(gameType).slice(0, 80);
  const safeState = String(stateSummary).slice(0, 600);
  const safeObjective = String(objective).slice(0, 200);
  return createHash("sha256").update([safeType, safeObjective, safeState].join("\n")).digest("hex");
}

function validActionKey(value) {
  return ACTION_KEYS.has(value) || /^click-cell:(?:[0-9]|[1-9][0-9])$/.test(value);
}

function validRecord(record) {
  return record && typeof record.id === "string" &&
    typeof record.gameType === "string" &&
    typeof record.stateKey === "string" && /^[a-f0-9]{64}$/.test(record.stateKey) &&
    typeof record.actionKey === "string" && validActionKey(record.actionKey) &&
    ["pending", "good", "bad"].includes(record.feedback);
}

/**
 * Small local-only experience ledger. It stores hashed state summaries and
 * keyboard actions only; never screenshots, page text, URLs, credentials or cookies.
 */
export function createGameExperienceMemory({ filePath = ".autoearn/experience-memory.json", now = () => new Date().toISOString() } = {}) {
  if (typeof filePath !== "string" || !filePath.trim()) throw new TypeError("A local memory file path is required.");
  let records = [];
  let loaded = false;

  async function save() {
    const directory = dirname(filePath);
    await mkdir(directory, { recursive: true });
    const temporary = filePath + ".tmp";
    await writeFile(temporary, JSON.stringify({ version: VERSION, records }, null, 2), { mode: 0o600 });
    await rename(temporary, filePath);
  }

  async function load() {
    if (loaded) return;
    try {
      const parsed = JSON.parse(await readFile(filePath, "utf8"));
      if (parsed?.version !== VERSION || !Array.isArray(parsed.records)) {
        throw new Error("Unsupported or invalid local experience memory format.");
      }
      records = parsed.records.filter(validRecord).slice(-MAX_RECORDS);
    } catch (error) {
      if (error.code !== "ENOENT") throw error;
      records = [];
    }
    loaded = true;
  }

  async function recordPending({ gameType, stateSummary, objective, action } = {}) {
    await load();
    if (typeof gameType !== "string" || !gameType.trim()) throw new TypeError("gameType is required.");
    let actionKey;
    if (action?.type === "press" && ACTION_KEYS.has(action.key)) {
      actionKey = action.key;
    } else if (action?.type === "click-cell" && Number.isInteger(action.index) && action.index >= 0 && action.index <= 99) {
      actionKey = `click-cell:${action.index}`;
    } else {
      throw new TypeError("Only allowlisted keyboard actions or indexed game-cell clicks can be remembered.");
    }
    const entry = {
      id: randomUUID(),
      gameType: gameType.slice(0, 80),
      stateKey: createStateKey({ gameType, stateSummary, objective }),
      actionKey,
      feedback: "pending",
      createdAt: now()
    };
    records.push(entry);
    records = records.slice(-MAX_RECORDS);
    await save();
    return entry.id;
  }

  async function rate(id, feedback) {
    await load();
    if (!["good", "bad"].includes(feedback)) throw new TypeError("Feedback must be good or bad.");
    const entry = records.find(item => item.id === id);
    if (!entry) throw new Error("Experience ID was not found in local memory.");
    if (entry.feedback !== "pending") throw new Error("This experience has already been rated.");
    entry.feedback = feedback;
    entry.ratedAt = now();
    await save();
    return { id: entry.id, feedback: entry.feedback };
  }

  async function getHints({ gameType, stateSummary, objective } = {}) {
    await load();
    const stateKey = createStateKey({ gameType, stateSummary, objective });
    const matching = records.filter(item => item.gameType === gameType && item.stateKey === stateKey && item.feedback !== "pending");
    const counts = new Map();
    for (const item of matching) {
      const current = counts.get(item.actionKey) || { good: 0, bad: 0 };
      current[item.feedback]++;
      counts.set(item.actionKey, current);
    }
    return [...counts.entries()]
      .map(([key, value]) => ({ key, good: value.good, bad: value.bad, net: value.good - value.bad }))
      .sort((a, b) => b.net - a.net || b.good - a.good)
      .slice(0, 5);
  }

  async function pending() {
    await load();
    return records.filter(item => item.feedback === "pending").map(({ id, gameType, actionKey, createdAt }) => ({
      id, gameType, actionKey, createdAt
    }));
  }

  return { load, recordPending, rate, getHints, pending };
}
