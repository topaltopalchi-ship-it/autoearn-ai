const BLOCKED_LABEL = /\b(log ?in|sign ?in|log ?out|sign ?out|register|sign ?up|account|profile|settings|password|payment|checkout|buy|purchase|deposit|withdraw|claim|redeem|submit|delete|remove|transfer|wallet|billing)\b|ورود|ثبت.?نام|حساب|پرداخت|خرید|واریز|برداشت|دریافت.?جایزه|حذف|انتقال|کیف.?پول/i;

export function isSafeNavigationTarget(target, approvedOrigin) {
  if (!target || typeof target !== "object") return false;
  const name = String(target.name || "").trim();
  if (!name || BLOCKED_LABEL.test(name)) return false;
  if (target.role === "link") {
    try {
      const url = new URL(target.href);
      return url.protocol === "https:" && url.origin === approvedOrigin;
    } catch {
      return false;
    }
  }
  return target.role === "button";
}

export async function collectNavigationTargets(page, approvedOrigin) {
  const raw = await page.locator('a[href],button,[role="link"],[role="button"]').evaluateAll(elements =>
    elements.map(element => {
      const role = element.getAttribute("role") ||
        (element.tagName.toLowerCase() === "a" ? "link" :
          element.tagName.toLowerCase() === "button" ? "button" : "");
      const name = element.getAttribute("aria-label") ||
        element.innerText || element.getAttribute("title") || "";
      return {
        role,
        name: String(name).replace(/\\s+/g, " ").trim().slice(0, 120),
        href: element.href || null,
        visible: Boolean(element.getClientRects().length) &&
          getComputedStyle(element).visibility !== "hidden"
      };
    })
  );
  const unique = new Map();
  for (const target of raw) {
    if (!target.visible || !isSafeNavigationTarget(target, approvedOrigin)) continue;
    const key = target.role + "\\0" + target.name + "\\0" + (target.href || "");
    if (!unique.has(key)) unique.set(key, { role: target.role, name: target.name, href: target.href });
  }
  return [...unique.values()].slice(0, 100);
}
