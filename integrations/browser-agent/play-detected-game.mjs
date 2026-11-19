import { chromium } from "playwright";
import "../../static/game-agent.js";
import { create2048BrowserAdapter } from "./2048-browser-adapter.mjs";
import { createTicTacToeBrowserAdapter } from "./tic-tac-toe-browser-adapter.mjs";
import { create2048Decision } from "./games/2048-strategy.mjs";
import { decideKnownGame } from "./games/game-strategy-registry.mjs";
import { detectKnownGame } from "./game-detector.mjs";
import { resolveDetectedGame } from "./game-runner-config.mjs";

const gameUrl = process.env.AUTOEARN_GAME_URL;
const allowedOrigins = new Set(String(process.env.AUTOEARN_ALLOWED_ORIGINS || "")
  .split(",").map(value => value.trim()).filter(Boolean));
const tttPlayer = String(process.env.AUTOEARN_TTT_PLAYER || "").toUpperCase();
const maxSteps = Math.min(500, Math.max(1, Number(process.env.AUTOEARN_MAX_STEPS || 100)));
const maxDurationMs = Math.min(5 * 60_000, Math.max(5_000, Number(process.env.AUTOEARN_MAX_DURATION_MS || 60_000)));

function validateTarget() {
  if (!gameUrl) throw new Error("Set AUTOEARN_GAME_URL.");
  if (process.env.AUTOEARN_AUTOMATION_APPROVED !== "YES") {
    throw new Error("Confirm the site's rules permit automated play by setting AUTOEARN_AUTOMATION_APPROVED=YES.");
  }
  const target = new URL(gameUrl);
  if (target.protocol !== "https:" || !allowedOrigins.has(target.origin)) {
    throw new Error("The game URL must match an explicitly approved HTTPS origin.");
  }
  return target;
}

async function assertSafePage(page, target, blocked) {
  if (blocked() || page.isClosed()) throw new Error("Browser safety guard stopped the game agent.");
  let currentOrigin;
  try {
    currentOrigin = new URL(page.url()).origin;
  } catch {
    throw new Error("Current page URL is invalid; stopping.");
  }
  if (currentOrigin !== target.origin) throw new Error("Page left the explicitly approved origin.");
  const text = ((await page.title().catch(() => "")) + "\\n" +
    (await page.locator("body").innerText().catch(() => ""))).toLowerCase();
  if (/captcha|verify you are human|robot check|security challenge|turnstile|hcaptcha|recaptcha/.test(text)) {
    throw new Error("Verification gate detected during play; stopping for human action.");
  }
}

async function inspectGame(page) {
  const candidates = await page.locator("body").evaluate(body =>
    Array.from(body.querySelectorAll("[data-game-board]")).slice(0, 10).map((board, index) => {
      const boardKey = board.getAttribute("data-game-board") || String(index);
      const cells = Array.from(board.querySelectorAll("[data-index]")).map(cell => ({
        index: cell.getAttribute("data-index"),
        mark: cell.getAttribute("data-mark") ?? cell.textContent
      }));
      const tiles = Array.from(board.querySelectorAll("[data-x][data-y][data-value]")).map(tile => ({
        x: tile.getAttribute("data-x"),
        y: tile.getAttribute("data-y"),
        value: tile.getAttribute("data-value")
      }));
      return cells.length ? { kind: "tic-tac-toe", boardKey, cells } :
        tiles.length ? { kind: "2048", boardKey, tiles } : null;
    }).filter(Boolean)
  );
  return detectKnownGame({ gameCandidates: candidates });
}

async function main() {
  const target = validateTarget();
  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext({ acceptDownloads: false });
  const page = await context.newPage();
  let blocked = false;
  context.on("page", popup => {
    if (popup !== page) {
      blocked = true;
      console.error("STOP: unexpected popup blocked.");
      void popup.close();
      void context.close();
    }
  });
  page.on("framenavigated", frame => {
    if (frame !== page.mainFrame()) return;
    try {
      if (new URL(frame.url()).origin !== target.origin) {
        blocked = true;
        void context.close();
      }
    } catch {
      blocked = true;
      void context.close();
    }
  });

  try {
    await page.goto(target.href, { waitUntil: "domcontentloaded", timeout: 20_000 });
    if (blocked || page.isClosed() || new URL(page.url()).origin !== target.origin) {
      throw new Error("Navigation left the approved origin.");
    }
    const pageText = ((await page.title().catch(() => "")) + "\n" +
      (await page.locator("body").innerText().catch(() => ""))).toLowerCase();
    if (/captcha|verify you are human|robot check|security challenge|turnstile|hcaptcha|recaptcha/.test(pageText)) {
      throw new Error("Verification gate detected; human action is required. No bypass was attempted.");
    }

    const detected = await inspectGame(page);
    const plan = resolveDetectedGame(detected, tttPlayer);
    if (!plan.ok) {
      throw new Error("Game runner refused to start: " + plan.reason);
    }

    let adapter;
    let decide;
    if (plan.adapter === "2048") {
      adapter = create2048BrowserAdapter(page, {
        boardSelector: "[data-game-board]",
        tileSelector: "[data-x][data-y][data-value]"
      });
      decide = create2048Decision();
    } else {
      adapter = createTicTacToeBrowserAdapter(page, {
        boardSelector: "[data-game-board]",
        cellSelector: "[data-index]",
        player: plan.player
      });
      decide = decideKnownGame;
    }

    const guardedAdapter = {
      async observe() {
        await assertSafePage(page, target, () => blocked);
        return adapter.observe();
      },
      async execute(action) {
        await assertSafePage(page, target, () => blocked);
        const result = await adapter.execute(action);
        await assertSafePage(page, target, () => blocked);
        return result;
      },
      ...(adapter.verify ? { verify: args => adapter.verify(args) } : {}),
      ...(adapter.isTerminal ? { isTerminal: observation => adapter.isTerminal(observation) } : {})
    };
    const initial = await guardedAdapter.observe();
    const agent = globalThis.AutoEarnGameAgent.createAgent({
      adapter: guardedAdapter,
      decide,
      limits: { maxSteps, maxDurationMs, allowedActions: plan.allowedActions },
      onEvent: event => {
        if (event.type === "step") console.log(JSON.stringify({
          step: event.steps, action: event.action.type,
          key: event.action.key, index: event.action.index,
          verified: event.verified
        }));
      }
    });
    console.log(JSON.stringify({
      status: "started", gameType: detected.gameType,
      detection: detected, initial: initial.gameState || initial.board
    }));
    const result = await agent.run();
    const finalState = await guardedAdapter.observe().catch(() => null);
    console.log(JSON.stringify({
      result, final: finalState?.gameState || finalState?.board || null,
      outcome: finalState?.gameState?.outcome || finalState?.outcome || "unknown"
    }, null, 2));
  } finally {
    await context.close().catch(() => {});
    await browser.close().catch(() => {});
  }
}

main().catch(error => {
  console.error(error.message || error);
  process.exitCode = 1;
});
