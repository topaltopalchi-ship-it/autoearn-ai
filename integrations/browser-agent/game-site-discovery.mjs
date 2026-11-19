import { detectKnownGame } from "./game-detector.mjs";

const GAME_HINT = /\b(game|games|play|puzzle|arcade|level|stage|folder|category|2048|tic.?tac.?toe|connect.?four)\b|بازی|بازی‌ها|بازیها|مرحله|مراحل|پوشه|دسته‌بندی|معما/i;
const GAME_PATH = /(?:^|\/)(?:games?|play|puzzles?|arcade|levels?|stages?|folders?|categories|2048|tic[-_]?tac[-_]?toe|connect[-_]?four)(?:\/|$)/i;
const BLOCKED_PATH = /(?:^|\/)(?:login|logout|signout|signin|register|signup|account|profile|checkout|purchase|payment|deposit|withdraw|claim|delete|remove|settings|admin)(?:\/|$)/i;
const VERIFY = /captcha|verify you are human|robot check|security challenge|cloudflare turnstile|hcaptcha|recaptcha|تأیید انسان|کد امنیتی/i;

export function selectGameNavigationLinks(links, { baseUrl, origin, maxLinks = 8 } = {}) {
  if (!Array.isArray(links) || typeof baseUrl !== "string" || typeof origin !== "string") return [];
  const base = new URL(baseUrl);
  if (base.origin !== origin || base.protocol !== "https:") return [];
  const result = [], seen = new Set([base.href]);
  for (const link of links) {
    if (result.length >= maxLinks) break;
    let url;
    try { url = new URL(String(link?.href || ""), base); } catch { continue; }
    if (url.protocol !== "https:" || url.origin !== origin || url.username || url.password) continue;
    url.search = ""; url.hash = "";
    if (BLOCKED_PATH.test(url.pathname) || seen.has(url.href)) continue;
    const label = [link?.label, link?.title, link?.ariaLabel].map(v => String(v || "")).join(" ");
    if (!(link?.gameLink === true || link?.folderLink === true || GAME_HINT.test(label) || GAME_PATH.test(url.pathname))) continue;
    seen.add(url.href);
    result.push({ url: url.href, label: label.trim().slice(0, 120) });
  }
  return result;
}

async function inspectPage(page, origin) {
  if (page.isClosed?.()) throw new Error("Page closed during game discovery.");
  const current = new URL(page.url());
  if (current.protocol !== "https:" || current.origin !== origin) {
    throw new Error("Game discovery stopped after navigation left the approved HTTPS origin.");
  }
  const title = await page.title().catch(() => "");
  const body = page.locator("body");
  const text = await body.innerText().catch(() => "");
  if (VERIFY.test(title + "\n" + text)) throw new Error("Verification or anti-bot gate found; human action is required.");
  const candidates = await body.evaluate(element => Array.from(element.querySelectorAll("[data-game-board]"))
    .slice(0, 10).map((board, index) => {
      const boardKey = board.getAttribute("data-game-board") || String(index);
      const connectFourCells = Array.from(board.querySelectorAll("[data-game-cell][data-game-cell-index]")).map(cell => ({
        index: cell.getAttribute("data-game-cell-index"),
        mark: cell.getAttribute("data-mark") ?? cell.textContent
      }));
      const othelloCells = Array.from(board.querySelectorAll("[data-game-cell][data-game-cell-index]")).map(cell => ({\n        index: cell.getAttribute("data-game-cell-index"),\n        mark: cell.getAttribute("data-mark") ?? cell.textContent\n      }));\n      const currentPlayer = board.getAttribute("data-current-player") || "";\n      const cells = Array.from(board.querySelectorAll("[data-index]")).map(cell => ({
        index: cell.getAttribute("data-index"),
        mark: cell.getAttribute("data-mark") ?? cell.textContent
      }));
      const tiles = Array.from(board.querySelectorAll("[data-x][data-y][data-value]")).map(tile => ({
        x: tile.getAttribute("data-x"), y: tile.getAttribute("data-y"), value: tile.getAttribute("data-value")
      }));
      if (connectFourCells.length === 42) return { kind: "connect-four", boardKey, cells: connectFourCells };\n      if (othelloCells.length === 64) return { kind: "othello", boardKey, cells: othelloCells, currentPlayer };
      if (cells.length) return { kind: "tic-tac-toe", boardKey, cells };
      if (tiles.length) return { kind: "2048", boardKey, tiles };
      return null;
    }).filter(Boolean)).catch(() => []);
  const links = await page.locator("a[href]").evaluateAll(anchors => anchors.map(anchor => ({
    href: anchor.href, label: (anchor.innerText || "").trim(),
    title: anchor.getAttribute("title") || "", ariaLabel: anchor.getAttribute("aria-label") || "",
    gameLink: anchor.hasAttribute("data-game-link"), folderLink: anchor.hasAttribute("data-game-folder")
  }))).catch(() => []);
  return { url: current.href, title: String(title).slice(0, 160), candidates, links };
}

export async function discoverSupportedGame(page, {
  startUrl = page?.url?.(), maxPages = 8, maxDepth = 2, maxDurationMs = 30_000
} = {}) {
  if (!page || typeof page.goto !== "function" || typeof startUrl !== "string") {
    throw new TypeError("A Playwright page and starting URL are required.");
  }
  if (!Number.isInteger(maxPages) || maxPages < 1 || maxPages > 12) throw new RangeError("maxPages must be from 1 to 12.");
  if (!Number.isInteger(maxDepth) || maxDepth < 0 || maxDepth > 3) throw new RangeError("maxDepth must be from 0 to 3.");
  if (!Number.isInteger(maxDurationMs) || maxDurationMs < 1_000 || maxDurationMs > 60_000) {
    throw new RangeError("maxDurationMs must be from 1000 to 60000.");
  }
  const start = new URL(startUrl);
  if (start.protocol !== "https:") throw new TypeError("Game discovery requires HTTPS.");
  const origin = start.origin, deadline = Date.now() + maxDurationMs;
  const queue = [{ url: start.href, depth: 0 }], visited = new Set(), pages = [], found = [];
  while (queue.length && pages.length < maxPages) {
    if (Date.now() > deadline) break;
    const next = queue.shift();
    if (visited.has(next.url)) continue;
    visited.add(next.url);
    await page.goto(next.url, { waitUntil: "domcontentloaded", timeout: Math.max(1_000, Math.min(8_000, deadline - Date.now())) });
    const inspected = await inspectPage(page, origin);
    pages.push({ url: inspected.url, title: inspected.title });
    const detected = detectKnownGame({ gameCandidates: inspected.candidates });
    if (detected.gameType) found.push({ url: inspected.url, title: inspected.title, detection: detected });
    if (next.depth < maxDepth) for (const link of selectGameNavigationLinks(inspected.links, {
      baseUrl: inspected.url, origin, maxLinks: 8
    })) if (!visited.has(link.url) && !queue.some(item => item.url === link.url)) {
      queue.push({ url: link.url, depth: next.depth + 1 });
    }
  }
  const unique = [...new Map(found.map(item => [item.url + ":" + item.detection.gameType + ":" + item.detection.boardKey, item])).values()];
  const selected = unique.length === 1 ? unique[0] : null;
  if (selected && page.url() !== selected.url) await page.goto(selected.url, { waitUntil: "domcontentloaded", timeout: 10_000 });
  else if (!selected && page.url() !== start.href) await page.goto(start.href, { waitUntil: "domcontentloaded", timeout: 10_000 });
  if (page.isClosed?.() || new URL(page.url()).origin !== origin) throw new Error("Could not safely finish game discovery on the approved origin.");
  return { selected, ambiguous: unique.length > 1, games: unique, pages, visitedUrls: [...visited] };
}
