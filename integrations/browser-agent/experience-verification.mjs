import { evaluateGameProgress } from "./game-progress-evaluator.mjs";

export function hasMeaningfulStateChange(before, after) {
  if (!before || !after) return false;
  const beforeState = before.gameState || {};
  const afterState = after.gameState || {};
  return before.url !== after.url ||
    before.snapshot !== after.snapshot ||
    beforeState.stateSummary !== afterState.stateSummary ||
    beforeState.objective !== afterState.objective ||
    beforeState.scene !== afterState.scene;
}

export async function recordVerifiedExperience(memory, pending, { before, action, after, onMemoryError = () => {} }) {
  if (!hasMeaningfulStateChange(before, after)) return false;
  if (!memory || typeof memory.recordPending !== "function") return true;
  const isKeyboardAction = action?.type === "press" && typeof action.key === "string";
  const isCellAction = action?.type === "click-cell" && Number.isInteger(action.index) && action.index >= 0 && action.index <= 99;
  const isCanvasAction = action?.type === "click-canvas" && Number.isFinite(action.x) && action.x >= 0 && action.x <= 1 &&
    Number.isFinite(action.y) && action.y >= 0 && action.y <= 1 && Number.isFinite(action.confidence) && action.confidence >= 0.8 && action.confidence <= 1;
  if (!isKeyboardAction && !isCellAction && !isCanvasAction) return true;
  const actionKey = isKeyboardAction ? action.key : isCellAction
    ? `click-cell:${action.index}`
    : `click-canvas:${Math.min(9, Math.floor(action.x * 10))}:${Math.min(9, Math.floor(action.y * 10))}`;
  const gameType = before.gameState?.gameType || "unknown";
  try {
    const id = await memory.recordPending({
      gameType,
      stateSummary: before.gameState?.stateSummary || "",
      objective: before.gameState?.objective || "",
      action
    });
    const progress = evaluateGameProgress(before, after);
    let feedbackStatus = "needs-review";
    // Only explicit, machine-readable terminal outcomes are strong enough for automatic rating.
    if (progress.confidence === 1 && ["good", "bad"].includes(progress.feedback)) {
      try {
        await memory.rate(id, progress.feedback);
        feedbackStatus = "auto-rated-explicit-outcome";
      } catch (error) {
        onMemoryError(error);
      }
    }
    pending?.push({ id, gameType, actionKey, progress, feedbackStatus });
  } catch (error) {
    onMemoryError(error);
  }
  return true;
}
