import test from "node:test";
import assert from "node:assert/strict";
import { createTicTacToeBrowserAdapter } from "../tic-tac-toe-browser-adapter.mjs";

function makePage(marks = Array(9).fill("")) {
  const cells = marks.map((mark, index) => ({
    mark,
    getAttribute(name) {
      if (name === "data-index") return String(index);
      if (name === "data-mark") return this.mark;
      return null;
    },
    get textContent() { return this.mark; },
    set textContent(value) { this.mark = value; }
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
  return {
    url: () => "https://game.example/ttt",
    locator: () => board,
    setMark(index, mark) { cells[index].mark = mark; }
  };
}

test("reads normalized 9-cell board and reports configured turn", async () => {
  const page = makePage(["X", "", "O", "", "X", "", "", "", ""]);
  const adapter = createTicTacToeBrowserAdapter(page, {
    boardSelector: "#board", cellSelector: ".cell", player: "O"
  });
  const state = await adapter.observe();
  assert.equal(state.gameState.type, "tic-tac-toe");
  assert.equal(state.gameState.currentPlayer, "O");
  assert.equal(state.gameState.outcome, "playing");
  assert.deepEqual(state.gameState.board, ["X", null, "O", null, "X", null, null, null, null]);
});

test("rejects wrong turn and invalid player configuration", async () => {
  const page = makePage(Array(9).fill(""));
  const adapter = createTicTacToeBrowserAdapter(page, {
    boardSelector: "#board", cellSelector: ".cell", player: "O"
  });
  const state = await adapter.observe();
  assert.equal(state.gameState.currentPlayer, "X");
  assert.equal(state.gameState.agentPlayer, "O");
  assert.throws(() => createTicTacToeBrowserAdapter(page, {
    boardSelector: "#board", cellSelector: ".cell", player: "Z"
  }), /player must be X or O/);
});

test("refuses to click before the configured player's turn", async () => {
  const page = makePage(Array(9).fill(""));
  const adapter = createTicTacToeBrowserAdapter(page, {
    boardSelector: "#board", cellSelector: ".cell", player: "O"
  });
  await assert.rejects(
    () => adapter.execute({ type: "select-cell", index: 4, mark: "O" }),
    /not the agent's turn/
  );
  const state = await adapter.observe();
  assert.equal(state.gameState.board[4], null);
  assert.equal(state.gameState.currentPlayer, "X");
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

test("wait-for-turn observes opponent move and verifies the next agent turn", async () => {
  const page = makePage(Array(9).fill(""));
  const adapter = createTicTacToeBrowserAdapter(page, {
    boardSelector: "#board", cellSelector: ".cell", player: "O"
  });
  const before = await adapter.observe();
  setTimeout(() => page.setMark(0, "X"), 100);
  const result = await adapter.execute({ type: "wait-for-turn" });
  const after = await adapter.observe();
  assert.equal(result.ready, true);
  assert.equal(after.gameState.currentPlayer, "O");
  assert.equal(await adapter.verify({
    before, after, action: { type: "wait-for-turn" }, result
  }), true);
});
