const HELP_LABEL = /\\b(help|instructions?|rules?|how to play|game guide|guide|tutorial|faq)\\b|راهنما|قوانین|چطور بازی|آموزش|دستورالعمل/i;
const HELP_PATH = /(?:^|\\/)(?:help|rules?|instructions?|guide|tutorial|how-to|faq|راهنما|قوانین|آموزش)(?:\\/|$)/i;
const SENSITIVE_PATH = /(?:logout|log-out|delete|remove|claim|checkout|purchase|deposit|withdraw|payment|submit|login|signin|sign-in|register|signup|sign-up|start-game|play-now)/i;
const VERIFICATION = /captcha|are you human|verify you are human|robot check|security challenge|cloudflare turnstile|hcaptcha|recaptcha|تأیید انسان|کد امنیتی/i;

function safeInstructionUrl(href, baseUrl, origin) {
  try {
    const url = new URL(href, baseUrl);
    if (url.protocol !== "https:" || url.origin !== origin || url.username || url.password) return null;
    url.search = "";
    url.hash = "";
    if (SENSITIVE_PATH.test(url.pathname)) return null;
    return url;
  } catch {
    return null;
  }
}

export function selectInstructionLinks(links, { baseUrl, origin, maxLinks = 5 } = {}) {
  if (!Array.isArray(links) || typeof baseUrl !== "string" || typeof origin !== "string") return [];
  const selected = [];
  const seen = new Set([new URL(baseUrl).href]);
  for (const link of links) {
    if (selected.length >= maxLinks) break;
    const label = String(link?.label || "") + " " + String(link?.title || "");
    const candidate = safeInstructionUrl(String(link?.href || ""), baseUrl, origin);
    if (!candidate || (!HELP_LABEL.test(label) && !HELP_PATH.test(candidate.pathname))) continue;
    if (seen.has(candidate.href)) continue;
    seen.add(candidate.href);
    selected.push({ url: candidate.href, label: label.trim().slice(0, 120) });
  }
  return selected;
}

async function readPage(page, origin) {
  const url = page.url();
  if (new URL(url).origin !== origin) throw new Error("Instruction discovery stopped after an origin change.");
  const title = await page.title().catch(() => "");
  const body = page.locator("body");
  const text = await body.innerText().catch(() => "");
  const snapshot = await body.ariaSnapshot().catch(() => "");
  if (VERIFICATION.test(title + "\\n" + text + "\\n" + snapshot)) {
    throw new Error("Verification or anti-bot gate found during instruction discovery; human action is required.");
  }
  const frameTexts = [];
  for (const frame of page.frames()) {
    if (frame === page.mainFrame()) continue;
    try {
      if (new URL(frame.url()).origin !== origin) continue;
      const frameText = await frame.locator("body").innerText().catch(() => "");
      if (frameText) frameTexts.push(frameText.slice(0, 4_000));
    } catch {}
  }
  const links = await page.locator("a[href]").evaluateAll(anchors => anchors.map(anchor => ({
    href: anchor.href,
    label: (anchor.innerText || anchor.getAttribute("aria-label") || "").trim(),
    title: anchor.getAttribute("title") || ""
  }))).catch(() => []);
  return {
    title: String(title).slice(0, 160),
    url,
    text: (String(text).slice(0, 8_000) + "\\n" + frameTexts.join("\\n").slice(0, 4_000)).slice(0, 10_000),
    snapshot: String(snapshot).slice(0, 5_000),
    links
  };
}

/**
 * Reads the current game page and a bounded set of clearly-labelled, same-origin
 * help/rules pages. It follows ordinary HTTPS links only; it never clicks buttons,
 * submits forms, signs in, or follows external links.
 */
export async function discoverGameInstructions(page, {
  startUrl = page?.url?.(),
  maxPages = 5,
  maxDurationMs = 20_000
} = {}) {
  if (!page || typeof page.goto !== "function" || typeof startUrl !== "string") {
    throw new TypeError("A Playwright page and starting URL are required.");
  }
  if (!Number.isInteger(maxPages) || maxPages < 1 || maxPages > 8) {
    throw new RangeError("maxPages must be from 1 to 8.");
  }
  if (!Number.isInteger(maxDurationMs) || maxDurationMs < 1_000 || maxDurationMs > 60_000) {
    throw new RangeError("maxDurationMs must be from 1000 to 60000.");
  }
  const start = new URL(startUrl);
  if (start.protocol !== "https:") throw new TypeError("Instruction discovery requires HTTPS.");
  const origin = start.origin;
  const deadline = Date.now() + maxDurationMs;
  const pages = [];
  const queue = [];
  const visited = new Set();

  const addPage = async () => {
    if (page.isClosed?.()) throw new Error("Browser page closed during instruction discovery.");
    if (Date.now() > deadline) throw new Error("Instruction discovery time budget exhausted.");
    const data = await readPage(page, origin);
    if (!visited.has(data.url)) {
      visited.add(data.url);
      pages.push(data);
    }
    for (const link of selectInstructionLinks(data.links, { baseUrl: data.url, origin, maxLinks: maxPages })) {
      if (!visited.has(link.url) && !queue.some(item => item.url === link.url)) queue.push(link);
    }
  };

  await addPage();
  while (queue.length && pages.length < maxPages) {
    if (Date.now() > deadline) break;
    const next = queue.shift();
    if (visited.has(next.url)) continue;
    await page.goto(next.url, { waitUntil: "domcontentloaded", timeout: Math.max(1_000, Math.min(5_000, deadline - Date.now())) });
    if (page.isClosed?.() || new URL(page.url()).origin !== origin) {
      throw new Error("Instruction discovery stopped because navigation left the approved origin.");
    }
    await addPage();
  }

  if (!page.isClosed?.() && page.url() !== start.href) {
    await page.goto(start.href, { waitUntil: "domcontentloaded", timeout: 10_000 });
    if (new URL(page.url()).origin !== origin) {
      throw new Error("Could not safely return to the original game page.");
    }
  }

  return {
    pages,
    visitedUrls: pages.map(item => item.url),
    title: pages[0]?.title || "",
    text: pages.map(item => "[صفحه: " + item.title + "]\\n" + item.text).join("\\n\\n").slice(0, 16_000),
    snapshot: pages.map(item => item.snapshot).filter(Boolean).join("\\n").slice(0, 8_000)
  };
}
