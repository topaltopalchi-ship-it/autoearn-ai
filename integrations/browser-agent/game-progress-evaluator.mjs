function validBox(item) {
  return item && ["x", "y", "width", "height", "confidence"].every(key => Number.isFinite(item[key])) &&
    item.x >= 0 && item.y >= 0 && item.width > 0 && item.height > 0 &&
    item.x + item.width <= 1 && item.y + item.height <= 1 &&
    item.confidence >= 0 && item.confidence <= 1;
}
function center(item) { return { x: item.x + item.width / 2, y: item.y + item.height / 2 }; }
function distance(a, b) {
  const p = center(a), q = center(b);
  return Math.hypot(p.x - q.x, p.y - q.y);
}
function overlaps(a, b) {
  return a.x < b.x + b.width && a.x + a.width > b.x &&
    a.y < b.y + b.height && a.y + a.height > b.y;
}

/**
 * Scores only observable geometric progress and explicit terminal outcomes.
 * This is a feedback suggestion, not a training label or proof of winning.
 */
export function evaluateGameProgress(before, after) {
  const signals = [];
  let reward = 0;
  const beforeOutcome = before?.gameState?.outcome;
  const afterOutcome = after?.gameState?.outcome;
  const explicitOutcome = after?.gameState?.outcomeSource === "dom-attribute";
  // A trusted terminal marker is authoritative: weaker geometry/metric signals
  // must never reverse a confirmed win or loss.
  if (explicitOutcome && afterOutcome === "won" && beforeOutcome !== "won") {
    return { reward: 3, feedback: "good", confidence: 1, signals: ["explicit-win"] };
  }
  if (explicitOutcome && afterOutcome === "lost" && beforeOutcome !== "lost") {
    return { reward: -3, feedback: "bad", confidence: 1, signals: ["explicit-loss"] };
  }
  if (afterOutcome === "won" && beforeOutcome !== "won") {
    signals.push("visible-win-hint");
    reward += 1;
  } else if (afterOutcome === "lost" && beforeOutcome !== "lost") {
    signals.push("visible-loss-hint");
    reward -= 1;
  }

  const oldObjects = Array.isArray(before?.canvasObjects) ? before.canvasObjects : [];
  const newObjects = Array.isArray(after?.canvasObjects) ? after.canvasObjects : [];
  const oldPlayer = oldObjects.find(item => item?.role === "player" && item.confidence >= 0.8 && validBox(item));
  const newPlayer = newObjects.find(item => item?.role === "player" && item.confidence >= 0.8 && validBox(item));
  const oldTarget = oldObjects.find(item => item?.role === "target" && item.confidence >= 0.75 && validBox(item));
  const newTarget = newObjects.find(item => item?.role === "target" && item.confidence >= 0.75 && validBox(item));

  if (oldPlayer && newPlayer && oldTarget && newTarget) {
    const oldDistance = distance(oldPlayer, oldTarget);
    const newDistance = distance(newPlayer, newTarget);
    if (newDistance + 0.015 < oldDistance) {
      reward += 1;
      signals.push("closer-to-target");
    } else if (newDistance > oldDistance + 0.015) {
      reward -= 1;
      signals.push("farther-from-target");
    }
  }

  const oldHazards = before?.canvasMotion?.predictedHazards || [];
  const newHazards = after?.canvasMotion?.predictedHazards || [];
  if (newPlayer && newHazards.some(h => h?.confidence >= 0.8 && validBox(h) && overlaps(newPlayer, h))) {
    reward -= 2;
    signals.push("predicted-hazard-overlap");
  } else if (oldPlayer && newPlayer &&
      oldHazards.some(h => h?.confidence >= 0.8 && validBox(h) && overlaps(oldPlayer, h)) &&
      !newHazards.some(h => h?.confidence >= 0.8 && validBox(h) && overlaps(newPlayer, h))) {
    reward += 1;
    signals.push("moved-away-from-hazard");
  }

  // Numeric metrics are trusted only when explicitly sourced from DOM attributes.
  const oldMetrics = before?.gameState?.metrics;
  const newMetrics = after?.gameState?.metrics;
  const trustedMetrics = before?.gameState?.metricsSource === "dom-attribute" &&
    after?.gameState?.metricsSource === "dom-attribute" &&
    oldMetrics && newMetrics && typeof oldMetrics === "object" && typeof newMetrics === "object";
  if (trustedMetrics) {
    for (const [key, direction, improvedSignal, worsenedSignal] of [
      ["score", 1, "score-increased", "score-decreased"],
      ["level", 1, "level-increased", "level-decreased"],
      ["lives", -1, "lives-decreased", "lives-increased"],
      ["mistakes", -1, "mistakes-decreased", "mistakes-increased"]
    ]) {
      const oldValue = oldMetrics[key], newValue = newMetrics[key];
      if (!Number.isFinite(oldValue) || !Number.isFinite(newValue) || oldValue === newValue) continue;
      const improved = (newValue - oldValue) * direction > 0;
      reward += improved ? 1 : -1;
      signals.push(improved ? improvedSignal : worsenedSignal);
    }
  }

  const feedback = reward >= 1 ? "good" : reward <= -1 ? "bad" : "neutral";
  return {
    reward,
    feedback,
    confidence: signals.length ? (signals.some(s => s.startsWith("explicit-")) ? 1 : 0.75) : 0,
    signals
  };
}
