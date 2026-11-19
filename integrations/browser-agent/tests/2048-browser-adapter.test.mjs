import test from "node:test";
import assert from "node:assert/strict";
import { create2048BrowserAdapter } from "../2048-browser-adapter.mjs";

function fakePage(cells, { boardCount = 1, onPress = async () => {} } = {}) {
  const elements = cells.map(cell => ({
    getAttribute(name) {
      if (name === "data-x") return cell.x ?? null;
      if (name === "data-y") return cell.y ?? null;
      if (name === "data-value") return cell.value ?? null;
      if (name === "aria-label") return cell.label ?? null;
      return null;
    },
    textContent: cell.text ?? ""
  }));
  const keys = [];
  const boardLocator = {
    async count() { return boardCount; },
    locator() {
      return { async evaluateAll(callback, attrs) { return callback(elements, attrs); } };
    }
  };
  return {
    keys,
    url: () => "https://game.example/2048",
    locator: () => boardLocator,
    keyboard: {
      async press(key) {
        keys.push(key);
        await onPress(key, cells);
      }
    }
  };
}

test("reads sparse DOM tiles into a complete 4x4 board", async () => {
  const page = fakePage([
    { x: "0", y: "0", value: "2" },
    { x: "1", y: "0", value: "4" },
    { x: "3", y: "2", value: "8" }
  ]);
  const adapter = create2048BrowserAdapter(page, { boardSelector: "#board", tileSelector: ".tile" });
  const state = await adapter.observe();
  assert.deepEqual(state.board, [
    [2, 4, 0, 0],
    [0, 0, 0, 0],
    [0, 0, 0, 8],
    [0, 0, 0, 0]
  ]);
  assert.equal(state.outcome, "playing");
});

test("supports one-based coordinates when explicitly configured", async () => {
  const page = fakePage([{ x: "1", y: "1", value: "2" }]);
  const adapter = create2048BrowserAdapter(page, {
    boardSelector: "#board", tileSelector: ".tile", coordinateBase: 1
  });
  assert.equal((await adapter.observe()).board[0][0], 2);
});

test("rejects missing coordinates instead of silently placing a tile at zero", async () => {
  const page = fakePage([{ y: "0", value: "2" }]);
  const adapter = create2048BrowserAdapter(page, { boardSelector: "#board", tileSelector: ".tile" });
  await assert.rejects(adapter.observe(), /explicit x\/y coordinates/);
});

test("rejects duplicate tile coordinates", async () => {
  const page = fakePage([
    { x: "0", y: "0", value: "2" },
    { x: "0", y: "0", value: "4" }
  ]);
  const adapter = create2048BrowserAdapter(page, { boardSelector: "#board", tileSelector: ".tile" });
  await assert.rejects(adapter.observe(), /Duplicate tile coordinates/);
});

test("requires exactly one board and valid positive tile values", async () => {
  const ambiguous = create2048BrowserAdapter(fakePage([], { boardCount: 2 }), {
    boardSelector: "#board", tileSelector: ".tile"
  });
  await assert.rejects(ambiguous.observe(), /exactly one element/);

  const invalid = create2048BrowserAdapter(fakePage([{ x: "0", y: "0", value: "3" }]), {
    boardSelector: "#board", tileSelector: ".tile"
  });
  await assert.rejects(invalid.observe(), /valid 4x4 2048 board/);
});

test("only permits arrow keys and verifies a changed board", async () => {
  const cells = [{ x: "0", y: "0", value: "2" }];
  const page = fakePage(cells, {
    onPress: async (key, current) => {
      if (key === "ArrowRight") current[0].x = "3";
    }
  });
  const adapter = create2048BrowserAdapter(page, { boardSelector: "#board", tileSelector: ".tile" });
  const before = await adapter.observe();
  await assert.rejects(adapter.execute({ type: "click", selector: "#claim" }), /only accepts arrow-key/);
  const result = await adapter.execute({ type: "press", key: "ArrowRight" });
  const after = await adapter.observe();
  assert.deepEqual(result, { key: "ArrowRight" });
  assert.equal(page.keys.length, 1);
  assert.equal(await adapter.verify({ before, after }), true);
});
