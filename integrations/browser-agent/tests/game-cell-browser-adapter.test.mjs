import test from "node:test";
import assert from "node:assert/strict";
import { clickSafeGameCell, readSafeGameCells, clickSafeGameCanvas } from "../game-cell-browser-adapter.mjs";

function makeElement(index, { label = "", hidden = false, nestedInteractive = false } = {}) {
  const parent = nestedInteractive ? {} : null;
  return {
    parentElement: parent,
    getAttribute(name) {
      if (name === "data-game-cell-index") return String(index);
      if (name === "aria-label") return label;
      return null;
    },
    get textContent() { return label; },
    hasAttribute: () => false,
    closest: selector => nestedInteractive && selector.includes("button") ? parent : null,
    getBoundingClientRect: () => ({ width: hidden ? 0 : 30, height: hidden ? 0 : 30 }),
    style: { display: hidden ? "none" : "block", visibility: "visible" }
  };
}

function fakePage(elements, { boardCount = 1 } = {}) {
  let clicked = null;
  const board = {
    count: async () => boardCount,
    locator: () => ({
      count: async () => elements.length,
      evaluateAll: async callback => callback(elements),
      evaluate: async callback => callback(elements[0]),
      click: async () => { clicked = elements[0]?.getAttribute("data-game-cell-index"); }
    })
  };
  return {
    locator: () => board,
    get clicked() { return clicked; }
  };
}

test("lists only visible, non-interactive, explicitly indexed cells", async () => {
  const page = fakePage([
    makeElement(0, { label: "empty cell" }),
    makeElement(1, { hidden: true }),
    makeElement(2, { nestedInteractive: true }),
    makeElement(3, { label: "safe cell" })
  ]);
  assert.deepEqual(await readSafeGameCells(page), [
    { index: 0, label: "empty cell", visible: true },
    { index: 3, label: "safe cell", visible: true }
  ]);
});

test("clicks exactly one indexed game cell inside exactly one board", async () => {
  const page = fakePage([makeElement(4)]);
  assert.deepEqual(await clickSafeGameCell(page, 4), { type: "click-cell", index: 4 });
  assert.equal(page.clicked, "4");
});

test("rejects arbitrary indices, ambiguous boards, and unsafe cells", async () => {
  await assert.rejects(() => clickSafeGameCell(fakePage([makeElement(1)]), 100), /0 to 99/);
  await assert.rejects(() => clickSafeGameCell(fakePage([makeElement(1)], { boardCount: 2 }), 1), /exactly one/);
  await assert.rejects(() => clickSafeGameCell(fakePage([makeElement(1, { nestedInteractive: true })]), 1), /Refusing to click/);
});

test("rejects missing or duplicate cell targets", async () => {
  await assert.rejects(() => clickSafeGameCell(fakePage([]), 2), /unique marked game cell/);
  await assert.rejects(() => clickSafeGameCell(fakePage([makeElement(2), makeElement(2)]), 2), /unique marked game cell/);
});


test("canvas click uses normalized coordinates inside one explicitly marked visible game canvas", async () => {
  let clickOptions;
  const canvas = {
    count: async () => 1,
    evaluate: async () => true,
    boundingBox: async () => ({ x: 10, y: 20, width: 200, height: 100 }),
    click: async options => { clickOptions = options; }
  };
  const page = { locator: selector => {
    assert.equal(selector, '[data-game-board] canvas[data-game-canvas]');
    return canvas;
  }};
  assert.deepEqual(await clickSafeGameCanvas(page, 0.25, 0.8, 0.92), {
    type: "click-canvas", x: 0.25, y: 0.8
  });
  assert.deepEqual(clickOptions, { position: { x: 50, y: 80 } });
});

test("refuses canvas clicks without one explicit canvas or with invalid coordinates", async () => {
  const page = { locator: () => ({ count: async () => 0 }) };
  await assert.rejects(() => clickSafeGameCanvas(page, 0.5, 0.5, 0.9), /exactly one/);
  await assert.rejects(() => clickSafeGameCanvas(page, -0.1, 0.5), /normalized/);
});


test("refuses canvas clicks when model confidence is below threshold", async () => {
  const page = { locator: () => ({ count: async () => 1 }) };
  await assert.rejects(() => clickSafeGameCanvas(page, 0.5, 0.5, 0.79), /confidence/);
});
