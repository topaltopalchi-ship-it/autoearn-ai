const MAX_CELL_INDEX = 99;

function validatePage(page) {
  if (!page || typeof page.locator !== "function") throw new TypeError("A Playwright Page is required.");
}

function safeCell(element) {
  const forbidden = element.closest("a,button,input,select,textarea,form,[role=button],[role=link]");
  const rect = element.getBoundingClientRect();
  const style = typeof getComputedStyle === "function" ? getComputedStyle(element) : (element.style || { display: "block", visibility: "visible" });
  return !forbidden && !element.hasAttribute("disabled") &&
    style.display !== "none" && style.visibility !== "hidden" &&
    rect.width > 0 && rect.height > 0;
}

export async function readSafeGameCells(page) {
  validatePage(page);
  const board = page.locator("[data-game-board]");
  if (await board.count() !== 1) return [];
  const cells = await board.locator("[data-game-cell][data-game-cell-index]").evaluateAll(elements =>
    elements.slice(0, 100).map(element => ({
      index: Number(element.getAttribute("data-game-cell-index")),
      label: (element.getAttribute("aria-label") || element.textContent || "").trim().slice(0, 80),
      visible: (() => {
        const forbidden = element.closest("a,button,input,select,textarea,form,[role=button],[role=link]");
        const rect = element.getBoundingClientRect();
        const style = typeof getComputedStyle === "function" ? getComputedStyle(element) : (element.style || { display: "block", visibility: "visible" });
        return !forbidden && !element.hasAttribute("disabled") &&
          style.display !== "none" && style.visibility !== "hidden" &&
          rect.width > 0 && rect.height > 0;
      })()
    }))
  );
  return cells.filter(cell => Number.isInteger(cell.index) && cell.index >= 0 &&
    cell.index <= MAX_CELL_INDEX && cell.visible);
}

export async function clickSafeGameCell(page, index) {
  validatePage(page);
  if (!Number.isInteger(index) || index < 0 || index > MAX_CELL_INDEX) {
    throw new RangeError("Game-cell index must be an integer from 0 to 99.");
  }
  const board = page.locator("[data-game-board]");
  if (await board.count() !== 1) throw new Error("Mouse action requires exactly one explicitly marked game board.");
  const cell = board.locator(`[data-game-cell][data-game-cell-index="${index}"]`);
  if (await cell.count() !== 1) throw new Error("Mouse action target is not one unique marked game cell.");
  if (!await cell.evaluate(safeCell)) {
    throw new Error("Refusing to click a hidden, disabled, or interactive non-cell element.");
  }
  await cell.click();
  return { type: "click-cell", index };
}
