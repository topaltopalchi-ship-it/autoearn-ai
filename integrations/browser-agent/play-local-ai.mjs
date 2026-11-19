import { chromium } from "playwright";
import "../../static/game-agent.js";
import { createOllamaGameDecision } from "./ollama-decision-provider.mjs";
import { createOllamaGamePerception } from "./ollama-game-perception.mjs";
import { createGameExperienceMemory } from "./game-experience-memory.mjs";

const gameUrl = process.env.AUTOEARN_GAME_URL;
const approvedOrigins = new Set(String(process.env.AUTOEARN_ALLOWED_ORIGINS || "")
  .split(",").map(value => value.trim()).filter(Boolean));
const model = process.env.AUTOEARN_LOCAL_MODEL;
const maxSteps = Math.min(300, Math.max(1, Number(process.env.AUTOEARN_MAX_STEPS || 80)));
const maxDurationMs = Math.min(5 * 60_000, Math.max(5_000, Number(process.env.AUTOEARN_MAX_DURATION_MS || 60_000)));
const maxModelCalls = Math.min(300, Math.max(1, Number(process.env.AUTOEARN_MAX_MODEL_CALLS || 80)));

function validateTarget() {
  if (!gameUrl || !model) throw new Error("Set AUTOEARN_GAME_URL and AUTOEARN_LOCAL_MODEL.");
  if (process.env.AUTOEARN_AUTOMATION_APPROVED !== "YES") {
    throw new Error("Confirm that the site's official rules permit automated play: set AUTOEARN_AUTOMATION_APPROVED=YES.");
  }
  const target = new URL(gameUrl);
  if (target.protocol !== "https:" || !approvedOrigins.has(target.origin)) {
    throw new Error("Game URL must match an explicitly approved exact HTTPS origin.");
  }
  return target;
}

function verificationGate(text) {
  return /captcha|are you human|verify you are human|robot check|security challenge|cloudflare turnstile|hcaptcha|recaptcha|تأیید انسان|کد امنیتی/i.test(text);
}

async function main() {
  const target = validateTarget();
  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext({ acceptDownloads: false });
  const page = await context.newPage();
  page.setDefaultTimeout(5_000);
  let blocked = false;

  const stopForBoundary = reason => {
    blocked = true;
    console.error("STOP: " + reason);
    void context.close();
  };
  context.on("page", popup => {
    if (popup !== page) {
      void popup.close();
      stopForBoundary("unexpected popup blocked");
    }
  });
  page.on("framenavigated", frame => {
    if (frame !== page.mainFrame()) return;
    try {
      if (new URL(frame.url()).origin !== target.origin) stopForBoundary("navigation left approved origin");
    } catch {
      stopForBoundary("invalid navigation target");
    }
  });

  try {
    await page.goto(target.href, { waitUntil: "domcontentloaded", timeout: 20_000 });
    if (blocked || page.isClosed() || new URL(page.url()).origin !== target.origin) {
      throw new Error("Navigation left the approved origin.");
    }

    const experienceMemory = createGameExperienceMemory({
      filePath: process.env.AUTOEARN_MEMORY_FILE || ".autoearn/experience-memory.json"
    });
    await experienceMemory.load();
    const pendingFeedback = [];
    const decide = createOllamaGameDecision({ model, maxCalls: maxModelCalls, experienceMemory });
    const perceive = createOllamaGamePerception({ model, maxCalls: maxModelCalls });
    const adapter = {
      async observe() {
        if (blocked || page.isClosed()) throw new Error("Browser session was stopped.");
        const title = await page.title().catch(() => "");
        const snapshot = await page.locator("body").ariaSnapshot().catch(() => "");
        const visibleText = await page.locator("body").innerText().catch(() => "");
        if (verificationGate(title + "\n" + snapshot + "\n" + visibleText)) {
          throw new Error("Verification or anti-bot gate detected. Human action is required; no bypass was attempted.");
        }
        const screenshot = await page.screenshot({ type: "jpeg", quality: 65, fullPage: false, timeout: 5_000 });
        const screenshotData = "data:image/jpeg;base64," + screenshot.toString("base64");
        const gameState = await perceive({ screenshot: screenshotData, title, text: visibleText });
        if (gameState.scene === "verification") {
          throw new Error("Local visual model detected a verification gate. Human action is required; no bypass was attempted.");
        }
        if (gameState.scene !== "game" || gameState.confidence < 0.65) {
          throw new Error("Local visual model could not confidently identify a playable game state; stopping instead of guessing.");
        }
        return {
          title,
          url: page.url(),
          snapshot: (snapshot + "\\nVisual state: " + gameState.stateSummary).slice(0, 10_000),
          text: (visibleText + "\\nObjective: " + gameState.objective + "\\nControls: " + gameState.controls.join(", ")).slice(0, 3_000),
          gameState,
          screenshot: screenshotData
        };
      },
      async execute(action) {
        if (blocked || page.isClosed()) throw new Error("Browser session was stopped.");
        if (!action || action.type !== "press" ||
            !["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "Enter", "Escape", " "].includes(action.key)) {
          throw new Error("Only allowlisted game keyboard actions are permitted.");
        }
        await page.keyboard.press(action.key === " " ? "Space" : action.key);
        return { type: "press", key: action.key };
      },
      async verify({ before, after }) {
        const verified = Boolean(after && before && (
          before.url !== after.url ||
          before.snapshot !== after.snapshot ||
          before.screenshot !== after.screenshot
        ));
        if (verified) {
          try {
            const id = await experienceMemory.recordPending({
              gameType: before.gameState?.gameType || "unknown",
              stateSummary: before.gameState?.stateSummary || "",
              objective: before.gameState?.objective || "",
              action
            });
            pendingFeedback.push({
              id,
              gameType: before.gameState?.gameType || "unknown",
              actionKey: action.key
            });
          } catch (error) {
            console.warn("Experience memory was not saved:", error.message);
          }
        }
        return verified;
      },
      isTerminal(observation) {
        return /game over|you win|you won|you lost|victory|defeat|بازی تمام شد|برنده شدی|باختی/i
          .test((observation?.snapshot || "") + "\n" + (observation?.text || ""));
      }
    };

    const agent = globalThis.AutoEarnGameAgent.createAgent({
      adapter,
      decide,
      limits: { maxSteps, maxDurationMs, allowedActions: ["press"] },
      onEvent: event => {
        if (event.type === "step") {
          console.log(JSON.stringify({
            step: event.steps,
            key: event.action?.key,
            verified: event.verified,
            localModelCalls: decide.usage.calls,
            localVisionCalls: perceive.usage.calls
          }));
        }
      }
    });

    const initial = await adapter.observe();
    console.log(JSON.stringify({ status: "ready", title: initial.title, url: initial.url, model }));
    const result = await agent.run();
    console.log(JSON.stringify({
      result,
      localModelUsage: decide.usage,
      localVisionUsage: perceive.usage,
      pendingExperienceFeedback: pendingFeedback,
      finalUrl: page.isClosed() ? null : page.url()
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
