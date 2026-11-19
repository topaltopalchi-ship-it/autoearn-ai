import { chromium } from "playwright";
import "../../static/game-agent.js";
import { createOllamaGameDecision } from "./ollama-decision-provider.mjs";
import { createOllamaGamePerception } from "./ollama-game-perception.mjs";
import { createOllamaGameRulesExtractor } from "./game-rule-extractor.mjs";
import { discoverGameInstructions } from "./game-instruction-discovery.mjs";
import { createGameExperienceMemory } from "./game-experience-memory.mjs";
import { recordVerifiedExperience } from "./experience-verification.mjs";
import { readSafeGameCells, clickSafeGameCell, clickSafeGameCanvas } from "./game-cell-browser-adapter.mjs";
import { detectGameOutcome } from "./game-outcome-detector.mjs";
import { mapViewportObjectsToCanvas } from "./canvas-object-mapper.mjs";
import { createCanvasMotionTracker } from "./canvas-motion-tracker.mjs";
import { planCanvasTactics } from "./canvas-tactical-planner.mjs";

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

function localGameStateKey(observation) {
  const state = observation?.gameState || {};
  const objects = (Array.isArray(observation?.canvasObjects) ? observation.canvasObjects : [])
    .filter(item => item && Number.isFinite(item.confidence) && item.confidence >= 0.8)
    .map(item => ({
      role: String(item.role || "other").slice(0, 20),
      label: String(item.label || "").slice(0, 30),
      x: Math.round((item.x || 0) * 50) / 50,
      y: Math.round((item.y || 0) * 50) / 50,
      width: Math.round((item.width || 0) * 50) / 50,
      height: Math.round((item.height || 0) * 50) / 50
    }))
    .sort((a, b) => a.role.localeCompare(b.role) || a.label.localeCompare(b.label));
  return JSON.stringify({
    gameType: String(state.gameType || "unknown").slice(0, 30),
    stateSummary: String(state.stateSummary || "").slice(0, 240),
    objective: String(state.objective || "").slice(0, 120),
    objects
  });
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
    const recentProgress = [];
    const decide = createOllamaGameDecision({ model, maxCalls: maxModelCalls, experienceMemory, allowCellClicks: true, allowCanvasClicks: true });
    const perceive = createOllamaGamePerception({ model, maxCalls: maxModelCalls });
    const extractRules = createOllamaGameRulesExtractor({ model, maxCalls: 3 });
    let extractedRules = null;
    const motionTracker = createCanvasMotionTracker({ horizonMs: 500 });
    const adapter = {
      getStateKey: localGameStateKey,
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
        const canvasLocator = page.locator("[data-game-board] canvas[data-game-canvas]");
        const canvasCount = await canvasLocator.count();
        const decisionScreenshot = canvasCount === 1
          ? "data:image/jpeg;base64," + (await canvasLocator.screenshot({ type: "jpeg", quality: 75, timeout: 5_000 })).toString("base64")
          : screenshotData;
        const gameState = await perceive({ screenshot: screenshotData, title, text: visibleText });
        const canvasObjects = canvasCount === 1
          ? mapViewportObjectsToCanvas(
              gameState.objects || [],
              await canvasLocator.boundingBox().catch(() => null),
              page.viewportSize()
            )
          : [];
        const canvasMotion = motionTracker.update(canvasObjects);
        const canvasTactics = planCanvasTactics({ objects: canvasObjects, motion: canvasMotion });

        const outcomeMarkers = await page.locator("[data-game-outcome], [data-game-status]").evaluateAll(elements =>
          elements.slice(0, 10).map(element => ({
            outcome: element.getAttribute("data-game-outcome") || "",
            status: element.getAttribute("data-game-status") || ""
          }))
        ).catch(() => []);
        const markerOutcomes = outcomeMarkers.map(marker => detectGameOutcome({
          outcomeAttribute: marker.outcome, statusAttribute: marker.status
        }));
        const domOutcome = markerOutcomes.find(result => ["won", "lost"].includes(result.outcome)) ||
          markerOutcomes.find(result => result.outcome === "playing") ||
          detectGameOutcome({ bodyText: visibleText });
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
          text: (visibleText + "\\nObjective: " + gameState.objective + "\\nControls: " + gameState.controls.join(", ") +
            (extractedRules ? "\\nPersian rules: " + extractedRules.summaryFa + "\\nGoal: " + extractedRules.objectiveFa +
              "\\nControls: " + extractedRules.controls.map(item => item.input + " = " + item.actionFa).join("; ") : "")).slice(0, 5_000),
          gameState: extractedRules ? {
            ...gameState,
            outcome: domOutcome.outcome,
            outcomeSource: domOutcome.source,
            objective: extractedRules.objectiveFa,
            stateSummary: gameState.stateSummary,
            rules: {
              summaryFa: extractedRules.summaryFa,
              controls: extractedRules.controls,
              scoringFa: extractedRules.scoringFa,
              winConditionFa: extractedRules.winConditionFa,
              loseConditionFa: extractedRules.loseConditionFa
            }
          } : { ...gameState, outcome: domOutcome.outcome, outcomeSource: domOutcome.source },
          rules: extractedRules,
          clickTargets: await readSafeGameCells(page),
          canvasAvailable: canvasCount === 1,
          canvasObjects,
          canvasMotion,
          canvasTactics,
          recentProgress: recentProgress.slice(-5),
          screenshot: screenshotData,
          decisionScreenshot
        };
      },
      async execute(action) {
        if (blocked || page.isClosed()) throw new Error("Browser session was stopped.");
        if (!action) throw new Error("An explicit game action is required.");
        if (action.type === "press" &&
            ["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "Enter", "Escape", " "].includes(action.key)) {
          await page.keyboard.press(action.key === " " ? "Space" : action.key);
          return { type: "press", key: action.key };
        }
        if (action.type === "click-cell" && Number.isInteger(action.index) && action.index >= 0 && action.index < 100) {
          await clickSafeGameCell(page, action.index);
          return { type: "click-cell", index: action.index };
        }
        if (action.type === "click-canvas" && Number.isFinite(action.x) && Number.isFinite(action.y)) {
          await clickSafeGameCanvas(page, action.x, action.y, action.confidence);
          return { type: "click-canvas", x: action.x, y: action.y };
        }
        throw new Error("Only allowlisted keyboard actions, explicitly marked game-cell clicks, or marked game-canvas clicks are permitted.");
      },
      async verify({ before, action, after }) {
        try {
          const verified = await recordVerifiedExperience(experienceMemory, pendingFeedback, { before, action, after });
          const latest = pendingFeedback[pendingFeedback.length - 1];
          if (verified && latest) {
            recentProgress.push({
              actionKey: latest.actionKey,
              feedback: latest.progress?.feedback || "neutral",
              confidence: latest.progress?.confidence || 0,
              signals: Array.isArray(latest.progress?.signals) ? latest.progress.signals.slice(0, 4) : []
            });
            if (recentProgress.length > 5) recentProgress.shift();
          }
          return verified;
        } catch (error) {
          console.warn("Experience memory was not saved:", error.message);
          return false;
        }
      },
      isTerminal(observation) {
        if (observation?.gameState?.outcomeSource && observation.gameState.outcome !== "unknown") {
          return ["won", "lost"].includes(observation.gameState.outcome);
        }
        return /game over|you win|you won|you lost|victory|defeat|بازی تمام شد|برنده شدی|باختی/i
          .test((observation?.snapshot || "") + "\\n" + (observation?.text || ""));
      }
    };

    const agent = globalThis.AutoEarnGameAgent.createAgent({
      adapter,
      decide,
      limits: { maxSteps, maxDurationMs, allowedActions: ["press", "click-cell", "click-canvas"] },
      onEvent: event => {
        if (event.type === "step") {
          console.log(JSON.stringify({
            step: event.steps,
            key: event.action?.key,
            cellIndex: event.action?.index,
            canvasPoint: event.action?.type === "click-canvas" ? { x: event.action.x, y: event.action.y } : undefined,
            actionType: event.action?.type,
            verified: event.verified,
            localModelCalls: decide.usage.calls,
            localVisionCalls: perceive.usage.calls
          }));
        }
      }
    });

    const instructionSet = await discoverGameInstructions(page, {
      startUrl: target.href,
      maxPages: 5,
      maxDurationMs: 20_000
    });
    const markedCanvas = page.locator("[data-game-board] canvas[data-game-canvas]");
    const canvasAvailable = await markedCanvas.count() === 1 && await markedCanvas.evaluate(element => {
      const rect = element.getBoundingClientRect();
      const style = getComputedStyle(element);
      return rect.width > 20 && rect.height > 20 && style.display !== "none" &&
        style.visibility !== "hidden" && style.pointerEvents !== "none" &&
        !element.closest("a,button,[role=button],[role=link],form");
    }).catch(() => false);
    extractedRules = await extractRules({
      title: instructionSet.title || await page.title().catch(() => ""),
      url: target.href,
      text: instructionSet.text,
      snapshot: instructionSet.snapshot,
      canvasAvailable
    });
    if (!extractedRules.rulesSufficient) {
      throw new Error("قوانین بازی به اندازه کافی روشن نیست؛ عامل برای جلوگیری از حرکت اشتباه متوقف شد. متن راهنما یا توضیحات کامل‌تری لازم است.");
    }
    if (extractedRules.automationPermission === "forbidden") {
      throw new Error("قوانین سایت استفاده از ربات را ممنوع کرده‌اند؛ بازی خودکار اجرا نشد.");
    }
    console.log(JSON.stringify({
      status: "rules-understood",
      title: instructionSet.title,
      url: target.href,
      instructionPages: instructionSet.visitedUrls,
      model,
      rules: extractedRules,
      ruleExtractionUsage: extractRules.usage
    }, null, 2));
    const initial = await adapter.observe();
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
