import test from "node:test";
import assert from "node:assert/strict";
import { createTicTacToeBrowserAdapter } from "../tic-tac-toe-browser-adapter.mjs";

function makePage(marks = Array(9).fill("")) {
  const cells = marks.map((mark, index) => ({
    getAttribute(name) {
      if (name === "data-index") return String(index);
      if (name === "data-mark") return mark;
      return null;
    },
    textContent: mark
  }));
  const board = {
    async count() { return 1; },
    locator(selector) {
      if (selector === ".cell") {
        return { async evaluateAll(callback, attrs) { return callback(cells, attrs); } };
      }
      const match = selector.match(/\.cell\[data-index="(\d+)"\]/);
      const cell = match ? cells[Number(match[1])] : null;
      return {
        async count() { return cell ? 1 : 0; },
        async getAttribute(name) { return cell?.getAttribute(name) ?? null; },
        async innerText() { return cell?.textContent ?? ""; },
        async click() { if (cell) { cell.getAttribute = name => name === "data-index" ? match[1] : name === "data-mark" ? "X" : null; cell.textContent = "X"; } }
      };
    }
  };
  return { url: () => "https://game.example/ttt", locator: () => board };
}

test("reads normalized 9-cell board and reports configured turn", async () => {
  const page = makePage(["X", "", "O", "", "X", "", "", "", ""]);
  const adapter = createTicTacToeBrowserAdapter(page, {
    boardSelector: "#board", cellSelector: ".cell", player: "O"
  });
  const state = await adapter.observe();
  assert.equal(state.gameState.currentPlayer, "O");
  assert.equal(state.gameState.outcome, "playing");
  assert.deepEqual(state.gameState.board, ["X", null, "O", null, "X", null, null, null, null]);
});

test("rejects wrong turn and invalid player configuration", async () => {
  const page = makePage(Array(9).fill(""));
  const adapter = createTicTacToeBrowserAdapter(page, {
    boardSelector: "#board", cellSelector: ".cell", player: "O"
  });
  await assert.rejects(adapter.observe(), /not the configured agent player's turn/);
  assert.throws(() => createTicTacToeBrowserAdapter(page, {
    boardSelector: "#board", cellSelector: ".cell", player: "Z"
  }), /player must be X or O/);
});

test("requires nine uniquely indexed cells", async () => {
  const page = makePage(Array(8).fill(""));
  const adapter = createTicTacToeBrowserAdapter(page, {
    boardSelector: "#board", cellSelector: ".cell", player: "X"
  });
  await assert.rejects(adapter.observe(), /exactly 9 cells/);
});

test("executes only a valid empty-cell action and verifies the mark", async () => {
  const page = makePage(Array(9).fill(""));
  const adapter = createTicTacToeBrowserAdapter(page, {
    boardSelector: "#board", cellSelector: ".cell", player: "X"
  });
  const before = await adapter.observe();
  const action = { type: "select-cell", index: 4, mark: "X" };
  await adapter.execute(action);
  const after = await adapter.observe();
  assert.equal(await adapter.verify({ before, after, action }), true);
  await assert.rejects(adapter.execute({ type: "select-cell", index: 99, mark: "X" }), /valid select-cell/);
});
