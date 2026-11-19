import { create2048Decision } from "./2048-strategy.mjs";
import { chooseTicTacToeMove, getTicTacToeOutcome } from "./tic-tac-toe-strategy.mjs";
import { chooseConnectFourMove, getConnectFourOutcome } from "./connect-four-strategy.mjs";

const strategies = new Map();

export function registerGameStrategy(gameType, strategy) {
  if (typeof gameType !== "string" || !/^[a-z0-9-]+$/.test(gameType)) {
    throw new TypeError("Game type must be a lowercase identifier.");
  }
  if (typeof strategy !== "function") throw new TypeError("Strategy must be a function.");
  strategies.set(gameType, strategy);
}

export function getGameStrategy(gameType) {
  return strategies.get(gameType) || null;
}

export async function decideKnownGame(observation) {
  const type = observation?.gameState?.type;
  const strategy = getGameStrategy(type);
  if (!strategy) return null;
  return strategy(observation.gameState);
}

registerGameStrategy("2048", async state => {
  if (!Array.isArray(state.board)) return null;
  return create2048Decision()(state);
});

registerGameStrategy("tic-tac-toe", async state => {
  if (!Array.isArray(state.board)) return null;
  if (state.agentPlayer && state.currentPlayer !== state.agentPlayer) {
    return { type: "wait-for-turn" };
  }
  const outcome = getTicTacToeOutcome(state.board);
  if (outcome !== "playing") return null;
  const move = chooseTicTacToeMove(state.board, { player: state.player });
  return move ? { type: "select-cell", index: move.index, mark: move.mark } : null;
});

registerGameStrategy("connect-four", async state => {
  if (!Array.isArray(state.board)) return null;
  if (state.agentPlayer && state.currentPlayer !== state.agentPlayer) return { type: "wait-for-turn" };
  if (getConnectFourOutcome(state.board) !== "playing") return null;
  const move = chooseConnectFourMove(state.board, { player: state.player, depth: 4 });
  return move ? { type: "click-column", column: move.column } : null;
});
