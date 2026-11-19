const MAX_TRACKS = 30;
const MAX_DELTA_MS = 2_000;
const PREDICTION_HORIZON_MS = 500;

function validBox(item) {
  return item && ["x", "y", "width", "height", "confidence"].every(key => Number.isFinite(item[key])) &&
    item.x >= 0 && item.y >= 0 && item.width > 0 && item.height > 0 &&
    item.x + item.width <= 1 && item.y + item.height <= 1 &&
    item.confidence >= 0 && item.confidence <= 1;
}
function center(item) { return { x: item.x + item.width / 2, y: item.y + item.height / 2 }; }
function clamp(value, low, high) { return Math.min(high, Math.max(low, value)); }

/** Tracks visible detections across observations and estimates short-horizon motion. */
export function createCanvasMotionTracker({ horizonMs = PREDICTION_HORIZON_MS, maxMatchDistance = 0.25 } = {}) {
  if (!Number.isFinite(horizonMs) || horizonMs < 100 || horizonMs > 2_000) throw new RangeError("horizonMs must be 100..2000.");
  if (!Number.isFinite(maxMatchDistance) || maxMatchDistance <= 0 || maxMatchDistance > 1) throw new RangeError("maxMatchDistance must be in (0,1].");
  let previous = [];
  let previousAt = null;
  let nextId = 1;
  const histories = new Map();

  return {
    update(objects, now = Date.now()) {
      if (!Number.isFinite(now)) throw new TypeError("A finite timestamp is required.");
      const current = (Array.isArray(objects) ? objects : []).filter(validBox).slice(0, MAX_TRACKS);
      const deltaMs = previousAt === null ? 0 : now - previousAt;
      const canCompare = deltaMs > 0 && deltaMs <= MAX_DELTA_MS;
      const used = new Set();
      const tracks = current.map(item => {
        const point = center(item);
        let match = null;
        let best = Infinity;
        if (canCompare) {
          for (const old of previous) {
            if (used.has(old.id) || old.role !== item.role || old.label !== (item.label || "")) continue;
            const oldPoint = center(old);
            const distance = Math.hypot(point.x - oldPoint.x, point.y - oldPoint.y);
            if (distance < best && distance <= maxMatchDistance) { best = distance; match = old; }
          }
        }
        const id = match?.id ?? nextId++;
        if (match) used.add(id);
        const vx = match ? (point.x - center(match).x) / deltaMs : 0;
        const vy = match ? (point.y - center(match).y) / deltaMs : 0;
        const lead = canCompare && match ? horizonMs : 0;
        const history = match ? (histories.get(id) || []).slice(-4) : [];
        history.push({ x: point.x, y: point.y, at: now });
        histories.set(id, history);
        const deltas = history.slice(1).map((sample, index) => ({
          x: sample.x - history[index].x,
          y: sample.y - history[index].y
        }));
        const reversals = axis => deltas.slice(1).filter((delta, index) =>
          Math.abs(deltas[index][axis]) > 0.002 && Math.abs(delta[axis]) > 0.002 &&
          Math.sign(deltas[index][axis]) !== Math.sign(delta[axis])
        ).length;
        const horizontalReversals = reversals("x");
        const verticalReversals = reversals("y");
        const pattern = horizontalReversals >= 2 || verticalReversals >= 2
          ? "oscillating"
          : Math.hypot(vx, vy) <= 0.00002 ? "stationary"
          : Math.abs(vx) > Math.abs(vy) * 1.8 ? "horizontal"
          : Math.abs(vy) > Math.abs(vx) * 1.8 ? "vertical" : "diagonal";
        const predictedCenterX = clamp(point.x + vx * lead, item.width / 2, 1 - item.width / 2);
        const predictedCenterY = clamp(point.y + vy * lead, item.height / 2, 1 - item.height / 2);
        return {
          id, role: item.role, label: (item.label || "").slice(0, 80),
          x: item.x, y: item.y, width: item.width, height: item.height,
          confidence: item.confidence,
          velocityX: vx * 1_000, velocityY: vy * 1_000,
          predicted: {
            x: predictedCenterX - item.width / 2,
            y: predictedCenterY - item.height / 2,
            width: item.width, height: item.height
          },
          moving: Boolean(match && Math.hypot(vx, vy) > 0.00002),
          pattern,
          samples: history.length
        };
      });
      const player = tracks.find(track => track.role === "player" && track.confidence >= 0.8);
      const previousPlayer = player ? previous.find(item => item.id === player.id) : null;
      const playerCenter = player ? center(player) : null;
      const previousPlayerCenter = previousPlayer ? center(previousPlayer) : null;
      if (playerCenter && previousPlayerCenter && canCompare) {
        for (const track of tracks) {
          if (!["hazard", "obstacle"].includes(track.role)) continue;
          const oldHazard = previous.find(item => item.id === track.id);
          if (!oldHazard) {
            track.approachingPlayer = false;
            continue;
          }
          const currentDistance = Math.hypot(center(track).x - playerCenter.x, center(track).y - playerCenter.y);
          const oldDistance = Math.hypot(center(oldHazard).x - previousPlayerCenter.x, center(oldHazard).y - previousPlayerCenter.y);
          track.approachingPlayer = currentDistance + 0.005 < oldDistance;
        }
      } else {
        for (const track of tracks) {
          if (["hazard", "obstacle"].includes(track.role)) track.approachingPlayer = false;
        }
      }
      const predictedPlayer = tracks.find(track => track.role === "player" && track.confidence >= 0.8);
      for (const track of tracks) {
        if (!["hazard", "obstacle"].includes(track.role)) continue;
        const p = predictedPlayer?.predicted;
        const h = track.predicted;
        track.collisionRisk = Boolean(p &&
          p.x < h.x + h.width && p.x + p.width > h.x &&
          p.y < h.y + h.height && p.y + p.height > h.y);
      }
      const activeIds = new Set(tracks.map(track => track.id));
      for (const id of histories.keys()) {
        if (!activeIds.has(id)) histories.delete(id);
      }
      previous = current.map((item, index) => ({ ...item, label: item.label || "", id: tracks[index].id }));
      previousAt = now;
      return {
        horizonMs: canCompare ? horizonMs : 0,
        tracks,
        predictedHazards: tracks.filter(track =>
          ["hazard", "obstacle"].includes(track.role) && track.confidence >= 0.8
        ).map(track => ({
          x: track.predicted.x, y: track.predicted.y,
          width: track.predicted.width, height: track.predicted.height,
          confidence: track.confidence, moving: track.moving,
          pattern: track.pattern, approachingPlayer: track.approachingPlayer === true,
          collisionRisk: track.collisionRisk === true
        }))
      };
    },
    reset() { previous = []; previousAt = null; histories.clear(); nextId = 1; }
  };
}
