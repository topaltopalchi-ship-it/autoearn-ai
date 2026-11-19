import { getConnectFourOutcome } from "./games/connect-four-strategy.mjs";

const MARKS = new Set(["X", "O"]);
const ROWS = 6;
const COLS = 7;

export function createConnectFourBrowserAdapter(page, {
  boardSelector = "[data-game-board]",
  cellSelector = "[data-game-cell][data-game-cell-index]",
  columnSelector = "[data-game-column][data-game-column-index]",
  player
} = {}) {
  if (!page || typeof page.locator !== "function") throw new TypeError("A Playwright Page is required.");
  if (!["X", "O"].includes(player)) throw new TypeError("player must be X or O.");
  async function readState() {
    const boardLocator = page.locator(boardSelector);
    if (await boardLocator.count() !== 1) throw new Error("Connect Four requires exactly one explicitly marked board.");
    const cells = await boardLocator.locator(cellSelector).evaluateAll(elements => elements.map(element => ({
      index: element.getAttribute("data-game-cell-index"),
      mark: element.getAttribute("data-mark") ?? element.textContent
    })));
    if (cells.length !== ROWS * COLS) throw new Error("Connect Four board must expose exactly 42 indexed cells.");
    const board = Array(ROWS * COLS).fill(null);
    for (const cell of cells) {
      if (cell.index === null || !/^\\d+$/.test(cell.index)) throw new Error("Every Connect Four cell needs an explicit numeric index.");
      const index = Number(cell.index);
      if (!Number.isInteger(index) || index < 0 || index >= ROWS * COLS || board[index] !== null) {
        throw new Error("Connect Four cell indices must be unique integers from 0 to 41.");
      }
      const raw = String(cell.mark || "").trim().toUpperCase();
      if (raw === "" || raw === "-" || raw === "EMPTY") board[index] = "";
      else if (MARKS.has(raw)) board[index] = raw;
      else throw new Error("Unrecognized Connect Four mark; refusing to guess.");
    }
    for (let col = 0; col < COLS; col++) {
      let emptySeen = false;
      for (let row = ROWS - 1; row >= 0; row--) {
        const value = board[row * COLS + col];
        if (!value) emptySeen = true;
        else if (emptySeen) throw new Error("Connect Four board violates gravity; refusing to act.");
      }
    }
    const xCount = board.filter(mark => mark === "X").length;
    const oCount = board.filter(mark => mark === "O").length;
    if (xCount < oCount || xCount - oCount > 1) throw new Error("Connect Four turn counts are inconsistent.");
    const currentPlayer = xCount === oCount ? "X" : "O";
    const outcome = getConnectFourOutcome(board);
    return { type: "connect-four", board, player: currentPlayer, agentPlayer: player, currentPlayer, outcome };
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
      if (action?.type !== "click-column" || !Number.isInteger(action.column) ||
          action.column < 0 || action.column >= COLS) {
        throw new Error("Only an explicitly indexed Connect Four column click is allowed.");
      }
      const state = await readState();
      if (state.outcome !== "playing" || state.currentPlayer !== player) throw new Error("It is not the agent's turn.");
      const column = page.locator(boardSelector).locator(
        `${columnSelector}[data-game-column-index="${action.column}"]`
      );
      if (await column.count() !== 1) throw new Error("Column target must be uniquely marked with data-game-column and data-game-column-index.");
      const safe = await column.evaluate(element => {
        const rect = element.getBoundingClientRect();
        const style = typeof getComputedStyle === "function" ? getComputedStyle(element) : (element.style || { display: "block", visibility: "visible" });
        return !element.hasAttribute("disabled") && element.getAttribute("aria-disabled") !== "true" &&
          style.display !== "none" && style.visibility !== "hidden" && rect.width > 0 && rect.height > 0;
      });
      if (!safe) throw new Error("Refusing to activate a hidden or disabled Connect Four column.");
      await column.click();
      return { column: action.column };
    },
    async verify({ before, after, action, result }) {
      if (action?.type === "wait-for-turn") {
        return result?.ready === true &&
          (after?.gameState?.outcome !== "playing" || after?.gameState?.currentPlayer === player);
      }
      const beforeBoard = before?.gameState?.board;
      const afterBoard = after?.gameState?.board;
      if (!Array.isArray(beforeBoard) || !Array.isArray(afterBoard) || action?.type !== "click-column") return false;
      const col = action.column;
      const changed = [];
      for (let index = 0; index < 42; index++) if (beforeBoard[index] !== afterBoard[index]) changed.push(index);
      const landing = (() => {
        for (let row = 5; row >= 0; row--) {
          const index = row * 7 + col;
          if (beforeBoard[index] === null || beforeBoard[index] === "") return index;
        }
        return -1;
      })();
      return changed.length === 1 && changed[0] === landing &&
        afterBoard[landing] === player &&
        beforeBoard.filter(Boolean).length + 1 === afterBoard.filter(Boolean).length;
    },
    isTerminal(observation) {
      return observation?.gameState?.outcome !== "playing";
    }
  };
}
