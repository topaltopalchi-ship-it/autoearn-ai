export function resolveDetectedGame(detected, player = "") {
  if (!detected || !["2048", "tic-tac-toe", "connect-four", "othello"].includes(detected.gameType)) {
    return { ok: false, reason: detected?.reason || "unsupported_or_ambiguous_game" };
  }
  if (detected.gameType === "2048") {
    return { ok: true, gameType: "2048", adapter: "2048", allowedActions: ["press"] };
  }
  const normalizedPlayer = String(player).toUpperCase();
  const validPlayers = detected.gameType === "othello" ? ["B", "W"] : ["X", "O"];
  if (!validPlayers.includes(normalizedPlayer)) {
    return { ok: false, reason: detected.gameType === "othello"
      ? "othello_player_must_be_B_or_W" : detected.gameType === "connect-four"
        ? "connect_four_player_must_be_X_or_O" : "tic_tac_toe_player_must_be_X_or_O" };
  }
  if (detected.gameType === "othello") {
    return {
      ok: true, gameType: "othello", adapter: "othello",
      player: normalizedPlayer, allowedActions: ["click-cell", "pass-turn", "wait-for-turn"]
    };
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
