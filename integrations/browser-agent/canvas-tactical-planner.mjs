const DIRECTIONS = [
  { key: "ArrowUp", dx: 0, dy: -1 },
  { key: "ArrowDown", dx: 0, dy: 1 },
  { key: "ArrowLeft", dx: -1, dy: 0 },
  { key: "ArrowRight", dx: 1, dy: 0 }
];

function validBox(box) {
  return box && ["x", "y", "width", "height"].every(key => Number.isFinite(box[key])) &&
    box.x >= 0 && box.y >= 0 && box.width > 0 && box.height > 0 &&
    box.x + box.width <= 1 && box.y + box.height <= 1;
}
function center(box) { return { x: box.x + box.width / 2, y: box.y + box.height / 2 }; }
function overlaps(a, b, padding = 0) {
  return a.x - padding < b.x + b.width && a.x + a.width + padding > b.x &&
    a.y - padding < b.y + b.height && a.y + a.height + padding > b.y;
}

/**
 * Produces conservative advisory tactics only; it does not issue browser actions
 * or claim that a route is safe in games with unknown physics.
 */
export function planCanvasTactics({ objects = [], motion = null, stepSize = 0.08 } = {}) {
  if (!Number.isFinite(stepSize) || stepSize < 0.01 || stepSize > 0.2) {
    throw new RangeError("stepSize must be between 0.01 and 0.2.");
  }
  const player = objects.find(item => item?.role === "player" && item.confidence >= 0.8 && validBox(item));
  if (!player) return { mode: "observe", suggestedKey: null, reason: "player-not-confidently-detected" };
  const hazards = (motion?.predictedHazards || [])
    .filter(item => item && item.confidence >= 0.8 && validBox(item)).slice(0, 30);
  const targets = objects.filter(item => item?.role === "target" && item.confidence >= 0.75 && validBox(item));
  const currentCenter = center(player);
  const target = targets.sort((a, b) =>
    Math.hypot(center(a).x - currentCenter.x, center(a).y - currentCenter.y) -
    Math.hypot(center(b).x - currentCenter.x, center(b).y - currentCenter.y)
  )[0] || null;
  const currentCollision = hazards.some(hazard => overlaps(player, hazard, 0.01));
  const candidates = DIRECTIONS.map(direction => {
    const x = Math.max(0, Math.min(1 - player.width, player.x + direction.dx * stepSize));
    const y = Math.max(0, Math.min(1 - player.height, player.y + direction.dy * stepSize));
    const next = { x, y, width: player.width, height: player.height };
    const collision = hazards.some(hazard => overlaps(next, hazard, 0.015));
    const distance = target
      ? Math.hypot(center({ ...next }).x - center(target).x, center({ ...next }).y - center(target).y)
      : 0;
    const hazardDistance = hazards.length
      ? Math.min(...hazards.map(hazard => Math.hypot(center(next).x - center(hazard).x, center(next).y - center(hazard).y)))
      : 1;
    return { key: direction.key, collision, distance, hazardDistance };
  });
  const safe = candidates.filter(candidate => !candidate.collision);
  if (currentCollision && safe.length === 0) {
    return { mode: "wait", suggestedKey: null, reason: "current-overlap-and-no-clear-direction", hazardCount: hazards.length };
  }
  if (!safe.length) {
    return { mode: "wait", suggestedKey: null, reason: "all-cardinal-steps-overlap-predicted-hazards", hazardCount: hazards.length };
  }
  safe.sort((a, b) => {
    const targetScore = target ? a.distance - b.distance : 0;
    const safetyScore = b.hazardDistance - a.hazardDistance;
    return targetScore * 0.65 + safetyScore * 0.35;
  });
  const best = safe[0];
  const mode = currentCollision || candidates.some(candidate => candidate.collision)
    ? "evade"
    : target ? "pursue" : "observe";
  return {
    mode,
    suggestedKey: best.key,
    reason: mode === "evade" ? "prefer-non-overlapping-step" :
      mode === "pursue" ? "move-toward-nearest-visible-target" : "no-confident-target",
    hazardCount: hazards.length,
    targetDetected: Boolean(target)
  };
}
