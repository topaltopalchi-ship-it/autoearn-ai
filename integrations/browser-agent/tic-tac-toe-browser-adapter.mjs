import { getTicTacToeOutcome } from "./games/tic-tac-toe-strategy.mjs";

const MARKS = new Set(["X", "O"]);

export function createTicTacToeBrowserAdapter(page, {
  boardSelector,
  cellSelector,
  indexAttribute = "data-index",
  markAttribute = "data-mark",
  player
} = {}) {
  if (!page || typeof page.locator !== "function") throw new TypeError("A Playwright Page is required.");
  if (typeof boardSelector !== "string" || !boardSelector.trim() ||
      typeof cellSelector !== "string" || !cellSelector.trim()) {
    throw new TypeError("Explicit boardSelector and cellSelector are required.");
  }
  if (!MARKS.has(player)) throw new TypeError("player must be X or O.");

  async function readState() {
    const boardLocator = page.locator(boardSelector);
    if (await boardLocator.count() !== 1) throw new Error("The configured tic-tac-toe board must match exactly one element.");
    const cells = await boardLocator.locator(cellSelector).evaluateAll((elements, attrs) =>
      elements.map(element => ({
        index: element.getAttribute(attrs.index),
        mark: element.getAttribute(attrs.mark),
        text: element.textContent
      })), { index: indexAttribute, mark: markAttribute });

    if (cells.length !== 9) throw new Error("Tic-tac-toe board must expose exactly 9 cells.");
    const board = Array(9).fill(null);
    for (const cell of cells) {
      if (cell.index === null || !/^\d+$/.test(cell.index)) {
        throw new Error("Every cell must expose an explicit numeric data-index from 0 to 8.");
      }
      const index = Number(cell.index);
      if (!Number.isInteger(index) || index < 0 || index > 8 || board[index] !== null) {
        throw new Error("Cell indices must be unique integers from 0 to 8.");
      }
      const raw = String(cell.mark || cell.text || "").trim().toUpperCase();
      if (raw === "" || raw === "-" || raw === "EMPTY") board[index] = null;
      else if (MARKS.has(raw)) board[index] = raw;
      else throw new Error("Unrecognized tic-tac-toe cell mark; refusing to guess.");
    }
    const xCount = board.filter(mark => mark === "X").length;
    const oCount = board.filter(mark => mark === "O").length;
    const currentPlayer = xCount === oCount ? "X" : "O";
    const outcome = getTicTacToeOutcome(board);
    return { type: "tic-tac-toe", board, player: currentPlayer, agentPlayer: player, currentPlayer, outcome };
  }

  return {
    async observe() {
      const gameState = await readState();
      return { url: page.url(), gameState };
    },
    async execute(action) {
      if (action?.type === "wait-for-turn") {
        const deadline = Date.now() + 30_000;
        while (Date.now() < deadline) {
          const state = await readState();
          if (state.outcome !== "playing" || state.currentPlayer === player) {
            return { ready: state.outcome !== "playing" || state.currentPlayer === player };
          }
          await new Promise(resolve => setTimeout(resolve, 250));
        }
        return { ready: false, timedOut: true };
      }
      if (action?.type !== "select-cell" || !Number.isInteger(action.index) ||
          action.index < 0 || action.index > 8 || action.mark !== player) {
        throw new Error("Only a valid select-cell or wait-for-turn action is allowed.");
      }
      const state = await readState();
      if (state.outcome !== "playing" || state.currentPlayer !== player) {
        throw new Error("It is not the agent's turn in this tic-tac-toe position.");
      }
      const board = page.locator(boardSelector);
      const cell = board.locator(`${cellSelector}[${indexAttribute}="${action.index}"]`);
      if (await cell.count() !== 1) throw new Error("Target cell must match exactly one element.");
      const markAttributeValue = await cell.getAttribute(markAttribute);
      const currentMark = String(markAttributeValue ?? await cell.innerText()).trim().toUpperCase();
      if (currentMark !== "" && currentMark !== "-" && currentMark !== "EMPTY") {
        throw new Error("Refusing to click a non-empty tic-tac-toe cell.");
      }
      await cell.click();
      return { index: action.index };
    },
    async verify({ before, after, action, result }) {
      if (action?.type === "wait-for-turn") {
        return result?.ready === true &&
          (after?.gameState?.outcome !== "playing" || after?.gameState?.currentPlayer === player);
      }
      const beforeBoard = before?.gameState?.board;
      const afterBoard = after?.gameState?.board;
      return before?.gameState?.outcome === "playing" &&
        before?.gameState?.currentPlayer === player &&
        Array.isArray(beforeBoard) && Array.isArray(afterBoard) &&
        beforeBoard[action.index] === null && afterBoard[action.index] === player &&
        beforeBoard.filter(Boolean).length + 1 === afterBoard.filter(Boolean).length;
    },
    isTerminal(observation) {
      return observation?.gameState?.outcome !== "playing";
    }
  };
}
