import { get2048Outcome } from "./games/2048-strategy.mjs";

const ARROW_KEYS = new Set(["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"]);

export function create2048BrowserAdapter(page, {
  boardSelector,
  tileSelector,
  xAttribute = "data-x",
  yAttribute = "data-y",
  valueAttribute = "data-value",
  coordinateBase = 0
} = {}) {
  if (!page || typeof page.locator !== "function") throw new TypeError("A Playwright Page is required.");
  if (typeof boardSelector !== "string" || !boardSelector.trim() ||
      typeof tileSelector !== "string" || !tileSelector.trim()) {
    throw new TypeError("Explicit boardSelector and tileSelector are required for site-specific mapping.");
  }

  async function readBoard() {
    const board = page.locator(boardSelector);
    if (await board.count() !== 1) throw new Error("The configured game board must match exactly one element.");
    const cells = await board.locator(tileSelector).evaluateAll((elements, attrs) => elements.map(element => ({
      x: element.getAttribute(attrs.x),
      y: element.getAttribute(attrs.y),
      value: element.getAttribute(attrs.value) ?? element.getAttribute("aria-label") ?? element.textContent
    })), { x: xAttribute, y: yAttribute, value: valueAttribute });
    const grid = Array.from({ length: 4 }, () => Array(4).fill(0));
    for (const cell of cells) {
      const x = Number(cell.x) - coordinateBase;
      const y = Number(cell.y) - coordinateBase;
      const match = String(cell.value || "").match(/\d+/);
      const value = match ? Number(match[0]) : 0;
      if (!Number.isInteger(x) || !Number.isInteger(y) || x < 0 || x > 3 || y < 0 || y > 3 ||
          !Number.isSafeInteger(value) || (value !== 0 && (value & (value - 1)) !== 0)) {
        throw new Error("The configured tile attributes do not describe a valid 4x4 2048 board.");
      }
      grid[y][x] = value;
    }
    return grid;
  }

  return {
    async observe() {
      const board = await readBoard();
      return { url: page.url(), board, outcome: get2048Outcome(board) };
    },
    async execute(action) {
      if (action?.type !== "press" || !ARROW_KEYS.has(action.key)) {
        throw new Error("2048 adapter only accepts arrow-key moves.");
      }
      await page.keyboard.press(action.key);
      return { key: action.key };
    },
    async verify({ before, after }) {
      return Boolean(before?.board && after?.board &&
        before.board.some((row, y) => row.some((value, x) => value !== after.board[y][x])));
    },
    isTerminal(observation) {
      return observation?.outcome === "won" || observation?.outcome === "game_over";
    }
  };
}
