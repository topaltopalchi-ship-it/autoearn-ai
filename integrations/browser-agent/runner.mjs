import { readDomGameMetrics } from "./dom-game-metrics.mjs";
import { chromium } from "playwright";
import { collectNavigationTargets } from "./site-navigation.mjs";
import { crawlSameOriginSite } from "./crawl-site.mjs";
import { validateApprovedTarget } from "./approved-url.mjs";

const gameUrl = process.env.AUTOEARN_GAME_URL;
const allowedOrigins = new Set(
  String(process.env.AUTOEARN_ALLOWED_ORIGINS || "")
    .split(",").map(value => value.trim()).filter(Boolean)
);
const maxPages = Math.min(30, Math.max(1, Number(process.env.AUTOEARN_MAX_PAGES || 12)));
const maxDepth = Math.min(6, Math.max(0, Number(process.env.AUTOEARN_MAX_DEPTH || 3)));
const maxDurationMs = Math.min(5 * 60_000, Math.max(5_000, Number(process.env.AUTOEARN_MAX_DURATION_MS || 60_000)));

function validateTarget(value) {
  return validateApprovedTarget(value, allowedOrigins);
}

function looksLikeVerificationGate(snapshot, title) {
  const text = (title + "\n" + snapshot).toLowerCase();
  return /captcha|are you human|verify you are human|robot check|bot detection|security challenge|cloudflare turnstile|hcaptcha|recaptcha/.test(text);
}

async function observe(page, origin) {
  const title = await page.title().catch(() => "");
  const snapshot = await page.locator("body").ariaSnapshot().catch(() => "");
  const navigationTargets = await collectNavigationTargets(page, origin).catch(() => []);
  const domSignals = await page.locator("body").evaluate(body => ({
    canvasCount: body.querySelectorAll("canvas").length,
    iframeCount: body.querySelectorAll("iframe").length,
    buttonCount: body.querySelectorAll('button,[role="button"]').length,
    inputCount: body.querySelectorAll("input,textarea,select").length,
    textSample: (body.innerText || "").slice(0, 4_000)
  })).catch(() => ({}));
  const gameCandidates = await page.locator("body").evaluate(body =>
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
  ).catch(() => []);
  const gameMetrics = await readDomGameMetrics(page).catch(() => null);
  return { title, url: page.url(), snapshot: snapshot.slice(0, 18_000), navigationTargets, domSignals, gameCandidates, ...(gameMetrics || {}) };
}

async function main() {
  if (!gameUrl || allowedOrigins.size === 0) {
    throw new Error("Set AUTOEARN_GAME_URL and AUTOEARN_ALLOWED_ORIGINS before starting.");
  }
  const target = validateTarget(gameUrl);
  const started = Date.now();
  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext({ acceptDownloads: false });
  const page = await context.newPage();
  page.setDefaultTimeout(5_000);
  let navigationBlocked = false;

  page.on("framenavigated", frame => {
    if (frame === page.mainFrame()) {
      try {
        if (new URL(frame.url()).origin !== target.origin) {
          navigationBlocked = true;
          console.error("STOP: navigation left the approved origin.");
          void context.close();
        }
      } catch {
        navigationBlocked = true;
        console.error("STOP: invalid navigation target.");
        void context.close();
      }
    }
  });

  try {
    const result = await crawlSameOriginSite({
      startUrl: target.href,
      approvedOrigin: target.origin,
      maxPages,
      maxDepth,
      maxDurationMs,
      maxInteractions: 20,
      expandFolderButton: async name => {
        if (navigationBlocked || page.isClosed()) return false;
        const button = page.getByRole("button", { name, exact: true });
        if (await button.count() !== 1) return false;
        const safe = await button.evaluate(element =>
          !element.closest("form") &&
          !(element.tagName.toLowerCase() === "button" && element.type === "submit") &&
          element.getAttribute("aria-disabled") !== "true"
        ).catch(() => false);
        if (!safe) return false;
        const beforeUrl = page.url();
        await button.click();
        if (navigationBlocked || page.isClosed() || new URL(page.url()).origin !== target.origin) {
          throw new Error("Folder expansion crossed the approved origin boundary.");
        }
        return page.url() === beforeUrl;
      },
      openPage: async url => {
        if (navigationBlocked || page.isClosed()) throw new Error("Browser navigation was stopped.");
        await page.goto(url, { waitUntil: "domcontentloaded", timeout: 20_000 });
        if (navigationBlocked || new URL(page.url()).origin !== target.origin) {
          throw new Error("Navigation outside approved origin.");
        }
      },
      inspectPage: () => observe(page, target.origin),
      isBlocked: observation => looksLikeVerificationGate(observation.snapshot || "", observation.title || "")
    });
    console.log(JSON.stringify(result, null, 2));
    if (Date.now() - started >= maxDurationMs) {
      console.log(JSON.stringify({ status: "limited", reason: "time_limit" }));
    }
  } finally {
    await context.close().catch(() => {});
    await browser.close().catch(() => {});
  }
}

main().catch(error => {
  console.error(error.message || error);
  process.exitCode = 1;
});
