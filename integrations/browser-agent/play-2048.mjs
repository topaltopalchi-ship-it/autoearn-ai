import { chromium } from "playwright";
import "../../static/game-agent.js";
import { create2048BrowserAdapter } from "./2048-browser-adapter.mjs";
import { create2048Decision } from "./games/2048-strategy.mjs";

const gameUrl = process.env.AUTOEARN_GAME_URL;
const allowedOrigins = new Set(String(process.env.AUTOEARN_ALLOWED_ORIGINS || "")
  .split(",").map(value => value.trim()).filter(Boolean));
const boardSelector = process.env.AUTOEARN_2048_BOARD_SELECTOR;
const tileSelector = process.env.AUTOEARN_2048_TILE_SELECTOR;
const maxSteps = Math.min(500, Math.max(1, Number(process.env.AUTOEARN_MAX_STEPS || 100)));
const maxDurationMs = Math.min(5 * 60_000, Math.max(5_000, Number(process.env.AUTOEARN_MAX_DURATION_MS || 60_000)));

function validateTarget() {
  if (!gameUrl || !boardSelector || !tileSelector) {
    throw new Error("Set AUTOEARN_GAME_URL, AUTOEARN_2048_BOARD_SELECTOR and AUTOEARN_2048_TILE_SELECTOR.");
  }
  if (process.env.AUTOEARN_AUTOMATION_APPROVED !== "YES") {
    throw new Error("Confirm the site's rules permit automated play by setting AUTOEARN_AUTOMATION_APPROVED=YES.");
  }
  const target = new URL(gameUrl);
  if (target.protocol !== "https:" || !allowedOrigins.has(target.origin)) {
    throw new Error("The game URL must match an explicitly approved HTTPS origin.");
  }
  return target;
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
    const text = ((await page.title().catch(() => "")) + "\n" +
      (await page.locator("body").innerText().catch(() => ""))).toLowerCase();
    if (/captcha|verify you are human|robot check|security challenge|turnstile|hcaptcha|recaptcha/.test(text)) {
      throw new Error("Verification gate detected; human action is required. No bypass was attempted.");
    }

    const adapter = create2048BrowserAdapter(page, { boardSelector, tileSelector });
    const initial = await adapter.observe();
    const agent = globalThis.AutoEarnGameAgent.createAgent({
      adapter,
      decide: create2048Decision(),
      limits: { maxSteps, maxDurationMs, allowedActions: ["press"] },
      onEvent: event => {
        if (event.type === "step") {
          console.log(JSON.stringify({
            step: event.steps,
            key: event.action.key,
            verified: event.verified
          }));
        }
      }
    });
    console.log(JSON.stringify({ status: "started", url: page.url(), initialBoard: initial.board }));
    const result = await agent.run();
    const finalState = await adapter.observe().catch(() => null);
    console.log(JSON.stringify({ result, finalBoard: finalState?.board || null }, null, 2));
  } finally {
    await context.close().catch(() => {});
    await browser.close().catch(() => {});
  }
}

main().catch(error => {
  console.error(error.message || error);
  process.exitCode = 1;
});
