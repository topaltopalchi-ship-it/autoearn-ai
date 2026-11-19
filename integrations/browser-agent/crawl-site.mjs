export async function crawlSameOriginSite({
  startUrl,
  approvedOrigin,
  openPage,
  inspectPage,
  isBlocked = () => false,
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
  const started = now();
  while (queue.length && pages.length < maxPages && now() - started < maxDurationMs) {
    const current = queue.shift();
    const normalized = new URL(current.url);
    normalized.hash = "";
    const url = normalized.href;
    if (visited.has(url)) continue;
    visited.add(url);
    if (normalized.origin !== approvedOrigin) continue;
    await openPage(url);
    const observation = await inspectPage();
    if (isBlocked(observation)) {
      return { status: "human_required", reason: "verification_gate_detected", pages, visited: [...visited] };
    }
    const targets = Array.isArray(observation?.navigationTargets) ? observation.navigationTargets : [];
    pages.push({
      url,
      depth: current.depth,
      title: String(observation?.title || "").slice(0, 200),
      targets
    });
    if (current.depth >= maxDepth) continue;
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
  const limited = queue.length > 0;
  return {
    status: limited ? "limited" : "completed",
    reason: limited ? (pages.length >= maxPages ? "page_limit" : "time_or_depth_limit") : "site_walk_finished",
    pages,
    visited: [...visited]
  };
}
