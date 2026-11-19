import test from "node:test";
import assert from "node:assert/strict";
import { createConnectFourBrowserAdapter } from "../connect-four-browser-adapter.mjs";

function makePage(board, { clickChangesBoard = true } = {}) {
  let state = board.flat();
  let clicked = null;
  const boardLocator = {
    count: async () => 1,
    locator(selector) {
      if (selector.startsWith("[data-game-cell]")) return {
        evaluateAll: async () => state.map((mark, index) => ({
          index: String(index), mark: mark || ""
        }))
      };
      const match = selector.match(/data-game-column-index="(\d+)"/);
      const column = match ? Number(match[1]) : -1;
      return {
        count: async () => column >= 0 && column < 7 ? 1 : 0,
        evaluate: async () => ({ }),
        click: async () => {
          clicked = column;
          if (clickChangesBoard) {
            for (let row = 5; row >= 0; row--) {
              const index = row * 7 + column;
              if (!state[index]) { state[index] = "X"; break; }
            }
          }
        }
      };
    }
  };
  return {
    locator: () => boardLocator,
    url: () => "https://game.example/connect-four",
    get clicked() { return clicked; }
  };
}
const empty = () => Array.from({ length: 6 }, () => Array(7).fill(""));

test("observes a valid 6x7 board and clicks only an explicitly marked column", async () => {
  const page = makePage(empty());
  const adapter = createConnectFourBrowserAdapter(page, { player: "X" });
  const before = await adapter.observe();
  assert.equal(before.gameState.type, "connect-four");
  await adapter.execute({ type: "click-column", column: 3 });
  const after = await adapter.observe();
  assert.equal(page.clicked, 3);
  assert.equal(await adapter.verify({ before, after, action: { type: "click-column", column: 3 }, result: {} }), true);
});

test("waits when it is the opponent's turn and refuses invalid columns", async () => {
  const board = empty();
  board[5][0] = "X";
  const page = makePage(board);
  const adapter = createConnectFourBrowserAdapter(page, { player: "X" });
  await assert.rejects(() => adapter.execute({ type: "click-column", column: 7 }), /explicitly indexed/);
  assert.equal(page.clicked, null);
});

test("refuses boards that do not expose 42 cells or violate gravity", async () => {
  const page = makePage(empty());
  const adapter = createConnectFourBrowserAdapter(page, { player: "X" });
  const original = page.locator;
  page.locator = () => ({ count: async () => 1, locator: () => ({ evaluateAll: async () => [{ index: "0", mark: "" }] }) });
  await assert.rejects(() => adapter.observe(), /exactly 42/);
  page.locator = original;
});
