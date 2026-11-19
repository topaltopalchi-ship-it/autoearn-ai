import { chromium } from "playwright";
import { collectNavigationTargets } from "./site-navigation.mjs";

const gameUrl = process.env.AUTOEARN_GAME_URL;
const allowedOrigins = new Set(
  String(process.env.AUTOEARN_ALLOWED_ORIGINS || "")
    .split(",").map(value => value.trim()).filter(Boolean)
);
const maxSteps = Math.min(200, Math.max(1, Number(process.env.AUTOEARN_MAX_STEPS || 40)));
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
  const text = (title + "\\n" + snapshot).toLowerCase();
  return /captcha|are you human|verify you are human|robot check|bot detection|security challenge|cloudflare turnstile|hcaptcha|recaptcha/.test(text);
}

async function observe(page, origin) {
  const title = await page.title().catch(() => "");
  const snapshot = await page.locator("body").ariaSnapshot().catch(() => "");
  const navigationTargets = await collectNavigationTargets(page, origin).catch(() => []);
  return { title, url: page.url(), snapshot: snapshot.slice(0, 18_000), navigationTargets };
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
  let steps = 0;
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
    await page.goto(target.href, { waitUntil: "domcontentloaded", timeout: 20_000 });
    while (steps < maxSteps && Date.now() - started < maxDurationMs && !page.isClosed() && !navigationBlocked) {
      const state = await observe(page, target.origin);
      if (navigationBlocked || new URL(state.url).origin !== target.origin) throw new Error("Navigation outside approved origin.");
      if (looksLikeVerificationGate(state.snapshot, state.title)) {
        console.log(JSON.stringify({ status: "human_required", reason: "verification_gate_detected" }, null, 2));
        break;
      }
      console.log(JSON.stringify({
        type: "site_observation",
        step: steps,
        url: state.url,
        title: state.title,
        navigationTargets: state.navigationTargets
      }, null, 2));
      console.log("Folder and category targets were discovered. No AI decision strategy is connected yet; stopping without clicking.");
      break;
    }
    if (steps >= maxSteps) console.log(JSON.stringify({ status: "limited", reason: "step_limit" }));
    else if (Date.now() - started >= maxDurationMs) console.log(JSON.stringify({ status: "limited", reason: "time_limit" }));
    else if (navigationBlocked) console.log(JSON.stringify({ status: "stopped", reason: "origin_boundary" }));
  } finally {
    await context.close().catch(() => {});
    await browser.close().catch(() => {});
  }
}

main().catch(error => {
  console.error(error.message || error);
  process.exitCode = 1;
});
