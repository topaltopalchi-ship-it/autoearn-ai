import { chromium } from "playwright";
import { collectNavigationTargets } from "./site-navigation.mjs";
import { crawlSameOriginSite } from "./crawl-site.mjs";

const gameUrl = process.env.AUTOEARN_GAME_URL;
const allowedOrigins = new Set(
  String(process.env.AUTOEARN_ALLOWED_ORIGINS || "")
    .split(",").map(value => value.trim()).filter(Boolean)
);
const maxPages = Math.min(30, Math.max(1, Number(process.env.AUTOEARN_MAX_PAGES || 12)));
const maxDepth = Math.min(6, Math.max(0, Number(process.env.AUTOEARN_MAX_DEPTH || 3)));
const maxDurationMs = Math.min(5 * 60_000, Math.max(5_000, Number(process.env.AUTOEARN_MAX_DURATION_MS || 60_000)));

function validateTarget(value) {
  let url;
  try { url = new URL(value); } catch { throw new Error("AUTOEARN_GAME_URL must be a valid URL."); }
  if (url.protocol !== "https:" || !allowedOrigins.has(url.origin)) {
    throw new Error("Target must use HTTPS and match an explicitly approved exact origin.");
  }
  return url;
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
  return { title, url: page.url(), snapshot: snapshot.slice(0, 18_000), navigationTargets, domSignals };
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
