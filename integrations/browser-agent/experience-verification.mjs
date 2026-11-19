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
  if (!isKeyboardAction && !isCellAction) return true;
  const actionKey = isKeyboardAction ? action.key : `click-cell:${action.index}`;
  const gameType = before.gameState?.gameType || "unknown";
  try {
    const id = await memory.recordPending({
      gameType,
      stateSummary: before.gameState?.stateSummary || "",
      objective: before.gameState?.objective || "",
      action
    });
    pending?.push({ id, gameType, actionKey });
  } catch (error) {
    onMemoryError(error);
  }
  return true;
}
