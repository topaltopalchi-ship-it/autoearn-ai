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
  if (!action || action.type !== "press" || typeof action.key !== "string") return true;
  const gameType = before.gameState?.gameType || "unknown";
  try {
    const id = await memory.recordPending({
      gameType,
      stateSummary: before.gameState?.stateSummary || "",
      objective: before.gameState?.objective || "",
      action
    });
    pending?.push({ id, gameType, actionKey: action.key });
  } catch (error) {
    onMemoryError(error);
  }
  return true;
}
