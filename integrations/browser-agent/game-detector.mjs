const TYPES = new Set(["tic-tac-toe", "2048", "connect-four", "othello"]);

function validIndexedCells(cells) {
  if (!Array.isArray(cells) || cells.length !== 9) return false;
  const indexes = new Set();
  for (const cell of cells) {
    const index = Number(cell.index);
    const mark = String(cell.mark ?? "").trim().toUpperCase();
    if (!Number.isInteger(index) || index < 0 || index > 8 || indexes.has(index) ||
        !["", "-", "EMPTY", "X", "O"].includes(mark)) return false;
    indexes.add(index);
  }
  return indexes.size === 9;
}

function validConnectFourCells(cells) {
  if (!Array.isArray(cells) || cells.length !== 42) return false;
  const indexes = new Set();
  for (const cell of cells) {
    const index = Number(cell.index);
    const mark = String(cell.mark ?? "").trim().toUpperCase();
    if (!Number.isInteger(index) || index < 0 || index > 41 || indexes.has(index) ||
        !["", "-", "EMPTY", "X", "O"].includes(mark)) return false;
    indexes.add(index);
  }
  if (indexes.size !== 42) return false;
  const board = Array.from({ length: 6 }, (_, row) =>
    Array.from({ length: 7 }, (_, col) => {
      const cell = cells.find(item => Number(item.index) === row * 7 + col);
      const mark = String(cell.mark ?? "").trim().toUpperCase();
      return ["", "-", "EMPTY"].includes(mark) ? "" : mark;
    })
  );
  for (let col = 0; col < 7; col++) {
    let foundGap = false;
    for (let row = 5; row >= 0; row--) {
      if (!board[row][col]) foundGap = true;
      else if (foundGap) return false;
    }
  }
  const wins = player => {
    for (let row = 0; row < 6; row++) for (let col = 0; col < 7; col++) {
      if (board[row][col] !== player) continue;
      for (const [dr, dc] of [[0,1],[1,0],[1,1],[1,-1]]) {
        let count = 1;
        for (let step = 1; step < 4; step++) {
          const r = row + dr * step, c = col + dc * step;
          if (r < 0 || r >= 6 || c < 0 || c >= 7 || board[r][c] !== player) break;
          count++;
        }
        if (count === 4) return true;
      }
    }
    return false;
  };
  return !(wins("X") && wins("O"));
}

function validOthelloCells(cells, currentPlayer) {
  if (!Array.isArray(cells) || cells.length !== 64 || !["B", "W", "BLACK", "WHITE"].includes(String(currentPlayer || "").toUpperCase())) return false;
  const indexes = new Set();
  for (const cell of cells) {
    const index = Number(cell.index), mark = String(cell.mark ?? "").trim().toUpperCase();
    if (!Number.isInteger(index) || index < 0 || index > 63 || indexes.has(index) ||
        !["", "-", "EMPTY", "B", "W", "BLACK", "WHITE", "X", "O"].includes(mark)) return false;
    indexes.add(index);
  }
  return indexes.size === 64;
}

function valid2048Tiles(tiles) {
  if (!Array.isArray(tiles) || tiles.length < 2 || tiles.length > 16) return false;
  const coordinates = new Set();
  for (const tile of tiles) {
    const x = Number(tile.x), y = Number(tile.y), value = Number(tile.value);
    const key = x + "," + y;
    if (!Number.isInteger(x) || x < 0 || x > 3 || !Number.isInteger(y) || y < 0 || y > 3 ||
        coordinates.has(key) || !Number.isSafeInteger(value) || value < 2 ||
        (value & (value - 1)) !== 0) return false;
    coordinates.add(key);
  }
  return true;
}

export function detectKnownGame(observation = {}) {
  const candidates = Array.isArray(observation.gameCandidates) ? observation.gameCandidates : [];
  const matches = [];
  for (const candidate of candidates) {
    if (!candidate || typeof candidate !== "object") continue;
    if (candidate.kind === "tic-tac-toe" && validIndexedCells(candidate.cells)) {
      matches.push({ gameType: "tic-tac-toe", boardKey: candidate.boardKey || null, confidence: 0.99 });
    }
    if (candidate.kind === "connect-four" && validConnectFourCells(candidate.cells)) {
      matches.push({ gameType: "connect-four", boardKey: candidate.boardKey || null, confidence: 0.99 });
    }
    if (candidate.kind === "othello" && validOthelloCells(candidate.cells, candidate.currentPlayer)) {
      matches.push({ gameType: "othello", boardKey: candidate.boardKey || null, confidence: 0.99 });
    }
    if (candidate.kind === "2048" && valid2048Tiles(candidate.tiles)) {
      matches.push({ gameType: "2048", boardKey: candidate.boardKey || null, confidence: 0.99 });
    }
  }
  const unique = [...new Map(matches.map(match => [match.gameType + ":" + String(match.boardKey), match])).values()];
  if (unique.length !== 1) return {
    gameType: null, confidence: 0,
    reason: unique.length > 1 ? "ambiguous_game_candidates" : "no_supported_board_signature",
    candidates: unique
  };
  return { ...unique[0], reason: "explicit_board_signature", candidates: unique };
}

export function isSupportedGameType(value) {
  return TYPES.has(value);
}
