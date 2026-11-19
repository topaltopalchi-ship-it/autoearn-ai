/** Pure, conservative dispatch for the detected game runner. */
export function resolveDetectedGame(detected, player = "") {
  if (!detected || !["2048", "tic-tac-toe"].includes(detected.gameType)) {
    return { ok: false, reason: detected?.reason || "unsupported_or_ambiguous_game" };
  }
  if (detected.gameType === "2048") {
    return {
      ok: true,
      gameType: "2048",
      adapter: "2048",
      allowedActions: ["press"]
    };
  }
  const normalizedPlayer = String(player).toUpperCase();
  if (!["X", "O"].includes(normalizedPlayer)) {
    return { ok: false, reason: "tic_tac_toe_player_must_be_X_or_O" };
  }
  return {
    ok: true,
    gameType: "tic-tac-toe",
    adapter: "tic-tac-toe",
    player: normalizedPlayer,
    allowedActions: ["select-cell", "wait-for-turn"]
  };
}
