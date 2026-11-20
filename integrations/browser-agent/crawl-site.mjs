import { classifySitePage } from "./page-classifier.mjs";
import { detectKnownGame } from "./game-detector.mjs";

const FOLDER_BUTTON_LABEL = /folder|category|categories|collection|library|arcade|room|level|پوشه|دسته|مجموعه|اتاق|مرحله/i;

export function isFolderExpandTarget(target) {
  return target?.role === "button" && FOLDER_BUTTON_LABEL.test(String(target.name || ""));
}

export async function crawlSameOriginSite({
  startUrl,
  approvedOrigin,
  openPage,
  inspectPage,
  isBlocked = () => false,
  expandFolderButton,
  maxInteractions = 20,
  maxPages = 12,
  maxDepth = 3,
  maxDurationMs = 45_000,
  now = () => Date.now()
}) {
  if (typeof openPage !== "function" || typeof inspectPage !== "function") {
    throw new TypeError("openPage and inspectPage callbacks are required.");
  }
  const start = new URL(startUrl);
  if (start.protocol !== "https:" || start.origin !== approvedOrigin) {
    throw new Error("Start URL must match the approved HTTPS origin.");
  }
  const queue = [{ url: start.href, depth: 0 }];
  const visited = new Set();
  const pages = [];
  const expandedControls = new Set();
  let interactions = 0;
  let depthTruncated = false;
  const started = now();
  while (queue.length && pages.length < maxPages && now() - started < maxDurationMs) {
    const current = queue.shift();
    const normalized = new URL(current.url);
    normalized.hash = "";
    const url = normalized.href;
    if (visited.has(url)) continue;
    visited.add(url);
    if (normalized.origin !== approvedOrigin || normalized.username || normalized.password || (normalized.port && normalized.port !== "443")) continue;
    await openPage(url);
    const observation = await inspectPage();
    if (isBlocked(observation)) {
      return { status: "human_required", reason: "verification_gate_detected", pages, visited: [...visited] };
    }
    let targets = Array.isArray(observation?.navigationTargets) ? [...observation.navigationTargets] : [];
    const classification = classifySitePage({ ...observation, url });
    const expandedButtons = [];
    if (classification.type === "folder" && typeof expandFolderButton === "function") {
      for (const button of targets.filter(isFolderExpandTarget)) {
        const key = url + "\\0" + button.name;
        if (expandedControls.has(key) || interactions >= maxInteractions) continue;
        expandedControls.add(key);
        interactions++;
        const expanded = await expandFolderButton(button.name);
        if (!expanded) continue;
        expandedButtons.push(button.name);
        const refreshed = await inspectPage();
        if (isBlocked(refreshed)) {
          return { status: "human_required", reason: "verification_gate_detected", pages, visited: [...visited] };
        }
        const refreshedTargets = Array.isArray(refreshed?.navigationTargets) ? refreshed.navigationTargets : [];
        const known = new Set(targets.map(target => target.role + "\\0" + target.name + "\\0" + (target.href || "")));
        for (const target of refreshedTargets) {
          const targetKey = target.role + "\\0" + target.name + "\\0" + (target.href || "");
          if (!known.has(targetKey)) targets.push(target);
        }
      }
    }
    pages.push({
      url,
      depth: current.depth,
      title: String(observation?.title || "").slice(0, 200),
      classification,
      gameDetection: detectKnownGame(observation),
      expandedButtons,
      targets
    });
    if (current.depth >= maxDepth) {
      if (targets.some(target => target.role === "link" && target.href)) depthTruncated = true;
      continue;
    }
    for (const target of targets) {
      if (target.role !== "link" || !target.href) continue;
      try {
        const next = new URL(target.href, url);
        next.hash = "";
        if (next.protocol !== "https:" || next.origin !== approvedOrigin) continue;
        if (!visited.has(next.href) && !queue.some(item => item.url === next.href)) {
          queue.push({ url: next.href, depth: current.depth + 1 });
        }
      } catch {
        // Ignore malformed navigation targets.
      }
    }
  }
  const limited = queue.length > 0 || depthTruncated;
  return {
    status: limited ? "limited" : "completed",
    reason: queue.length && pages.length >= maxPages ? "page_limit" :
      depthTruncated ? "depth_limit" : queue.length ? "time_limit" : "site_walk_finished",
    pages,
    visited: [...visited]
  };
}
