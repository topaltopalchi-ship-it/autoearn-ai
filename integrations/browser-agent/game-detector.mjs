const TYPES = new Set(["tic-tac-toe", "2048"]);

function validIndexedCells(cells) {
  if (!Array.isArray(cells) || cells.length !== 9) return false;
  const indexes = new Set();
  for (const cell of cells) {
    const index = Number(cell.index);
    const mark = String(cell.mark ?? "").trim().toUpperCase();
    if (!Number.isInteger(index) || index < 0 || index > 8 || indexes.has(index)) return false;
    if (!["", "-", "EMPTY", "X", "O"].includes(mark)) return false;
    indexes.add(index);
  }
  return indexes.size === 9;
}

function valid2048Tiles(tiles) {
  if (!Array.isArray(tiles) || tiles.length < 2 || tiles.length > 16) return false;
  const coordinates = new Set();
  for (const tile of tiles) {
    const x = Number(tile.x);
    const y = Number(tile.y);
    const value = Number(tile.value);
    const key = x + "," + y;
    if (!Number.isInteger(x) || x < 0 || x > 3 || !Number.isInteger(y) || y < 0 || y > 3 ||
        coordinates.has(key) || !Number.isSafeInteger(value) || value < 2 ||
        (value & (value - 1)) !== 0) return false;
    coordinates.add(key);
  }
  return true;
}

/**
 * Conservative recognition only. It never infers a playable game from page text alone.
 * A site must expose a marked board candidate with explicit cell/tile metadata.
 */
export function detectKnownGame(observation = {}) {
  const candidates = Array.isArray(observation.gameCandidates) ? observation.gameCandidates : [];
  const matches = [];
  for (const candidate of candidates) {
    if (!candidate || typeof candidate !== "object") continue;
    if (candidate.kind === "tic-tac-toe" && validIndexedCells(candidate.cells)) {
      matches.push({ gameType: "tic-tac-toe", boardKey: candidate.boardKey || null, confidence: 0.99 });
    }
    if (candidate.kind === "2048" && valid2048Tiles(candidate.tiles)) {
      matches.push({ gameType: "2048", boardKey: candidate.boardKey || null, confidence: 0.99 });
    }
  }
  const unique = [...new Map(matches.map(match => [match.gameType + ":" + String(match.boardKey), match])).values()];
  if (unique.length !== 1) {
    return {
      gameType: null,
      confidence: 0,
      reason: unique.length > 1 ? "ambiguous_game_candidates" : "no_supported_board_signature",
      candidates: unique
    };
  }
  return { ...unique[0], reason: "explicit_board_signature", candidates: unique };
}

export function isSupportedGameType(value) {
  return TYPES.has(value);
}
