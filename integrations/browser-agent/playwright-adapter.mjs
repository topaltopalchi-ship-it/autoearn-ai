import { collectNavigationTargets, isSafeNavigationTarget } from "./site-navigation.mjs";

const ALLOWED_KEYS = new Set(["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "Enter", "Space", "Escape"]);

export function createPlaywrightGameAdapter(page, { isTerminal = () => false } = {}) {
  if (!page || typeof page.locator !== "function") {
    throw new TypeError("A Playwright Page is required.");
  }

  return {
    async observe() {
      const title = await page.title().catch(() => "");
      const snapshot = await page.locator("body").ariaSnapshot().catch(() => "");
      const origin = new URL(page.url()).origin;
      const navigationTargets = await collectNavigationTargets(page, origin).catch(() => []);
      return { title, url: page.url(), snapshot: snapshot.slice(0, 18_000), navigationTargets };
    },

    async execute(action) {
      if (!action || typeof action !== "object") {
        throw new TypeError("A structured game action is required.");
      }

      if (action.type === "click") {
        if (!["button", "link"].includes(action.role) || typeof action.name !== "string" || !action.name.trim()) {
          throw new Error("Use an exact accessible name for a safe button or same-origin link.");
        }
        const origin = new URL(page.url()).origin;
        const candidate = { role: action.role, name: action.name, href: action.href };
        if (!isSafeNavigationTarget(candidate, origin)) {
          throw new Error("Navigation target is outside the approved origin or is a sensitive action.");
        }
        const target = page.getByRole(action.role, { name: action.name, exact: true });
        const count = await target.count();
        if (count !== 1) throw new Error("Target must match exactly one accessible element.");
        if (action.role === "link") {
          const actualHref = await target.getAttribute("href");
          const resolved = new URL(actualHref, page.url());
          if (resolved.origin !== origin) throw new Error("Cross-origin links are blocked.");
        }
        await target.click();
        if (new URL(page.url()).origin !== origin) throw new Error("Navigation left the approved origin.");
        return { type: "click", role: action.role, name: action.name };
      }

      if (action.type === "press") {
        if (!ALLOWED_KEYS.has(action.key)) throw new Error("Keyboard action is not allowlisted.");
        await page.keyboard.press(action.key);
        return { type: "press", key: action.key };
      }

      throw new Error("Unsupported browser game action.");
    },

    async verify({ before, after }) {
      return Boolean(after && before &&
        (after.url !== before.url || after.snapshot !== before.snapshot || isTerminal(after)));
    },

    isTerminal
  };
}
