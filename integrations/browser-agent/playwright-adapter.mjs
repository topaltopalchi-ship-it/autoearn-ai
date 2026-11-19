const ALLOWED_KEYS = new Set(["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "Enter", "Space", "Escape"]);

export function createPlaywrightGameAdapter(page, { isTerminal = () => false } = {}) {
  if (!page || typeof page.locator !== "function") {
    throw new TypeError("A Playwright Page is required.");
  }

  return {
    async observe() {
      const title = await page.title().catch(() => "");
      const snapshot = await page.locator("body").ariaSnapshot({ mode: "ai" });
      return { title, url: page.url(), snapshot: snapshot.slice(0, 18_000) };
    },

    async execute(action) {
      if (!action || typeof action !== "object") {
        throw new TypeError("A structured game action is required.");
      }

      if (action.type === "click") {
        if (action.role !== "button" || typeof action.name !== "string" || !action.name.trim()) {
          throw new Error("Only exact accessible-name button clicks are supported.");
        }
        const target = page.getByRole("button", { name: action.name, exact: true });
        const count = await target.count();
        if (count !== 1) throw new Error("Button target must match exactly one element.");
        await target.click();
        return { type: "click", role: "button", name: action.name };
      }

      if (action.type === "press") {
        if (!ALLOWED_KEYS.has(action.key)) throw new Error("Keyboard action is not allowlisted.");
        await page.keyboard.press(action.key);
        return { type: "press", key: action.key };
      }

      throw new Error("Unsupported browser game action.");
    },

    async verify({ before, after }) {
      return Boolean(after && before && after.url === before.url &&
        (after.snapshot !== before.snapshot || isTerminal(after)));
    },

    isTerminal
  };
}
