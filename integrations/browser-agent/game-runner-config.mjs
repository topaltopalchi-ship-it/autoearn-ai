export function resolveDetectedGame(detected, player = "") {
  if (!detected || !["2048", "tic-tac-toe", "connect-four"].includes(detected.gameType)) {
    return { ok: false, reason: detected?.reason || "unsupported_or_ambiguous_game" };
  }
  if (detected.gameType === "2048") {
    return { ok: true, gameType: "2048", adapter: "2048", allowedActions: ["press"] };
  }
  const normalizedPlayer = String(player).toUpperCase();
  if (!["X", "O"].includes(normalizedPlayer)) {
    return { ok: false, reason: detected.gameType === "connect-four"
      ? "connect_four_player_must_be_X_or_O" : "tic_tac_toe_player_must_be_X_or_O" };
  }
  if (detected.gameType === "connect-four") {
    return {
      ok: true, gameType: "connect-four", adapter: "connect-four",
      player: normalizedPlayer, allowedActions: ["click-column", "wait-for-turn"]
    };
  }
  return {
    ok: true, gameType: "tic-tac-toe", adapter: "tic-tac-toe",
    player: normalizedPlayer, allowedActions: ["select-cell", "wait-for-turn"]
  };
}
