const ROWS = 6;
const COLS = 7;
const EMPTY = "";
const ORDER = [3, 2, 4, 1, 5, 0, 6];

function normalizeBoard(board) {
  if (!Array.isArray(board)) throw new TypeError("Connect Four board must be an array.");
  const rows = board.length === ROWS && board.every(row => Array.isArray(row) && row.length === COLS)
    ? board.map(row => row.map(value => String(value ?? "").toUpperCase()))
    : board.length === ROWS * COLS
      ? Array.from({ length: ROWS }, (_, r) => board.slice(r * COLS, (r + 1) * COLS).map(value => String(value ?? "").toUpperCase()))
      : null;
  if (!rows || rows.some(row => row.some(value => !["", "-", "EMPTY", "X", "O"].includes(value)))) {
    throw new TypeError("Connect Four board must contain 42 valid X/O/empty cells.");
  }
  return rows.map(row => row.map(value => ["", "-", "EMPTY"].includes(value) ? EMPTY : value));
}

function landingRow(board, col) {
  for (let row = ROWS - 1; row >= 0; row--) if (!board[row][col]) return row;
  return -1;
}

function hasFour(board, player) {
  for (let r = 0; r < ROWS; r++) for (let c = 0; c < COLS; c++) {
    if (board[r][c] !== player) continue;
    for (const [dr, dc] of [[0,1],[1,0],[1,1],[1,-1]]) {
      let count = 1;
      for (let k = 1; k < 4; k++) {
        const nr = r + dr*k, nc = c + dc*k;
        if (nr < 0 || nr >= ROWS || nc < 0 || nc >= COLS || board[nr][nc] !== player) break;
        count++;
      }
      if (count === 4) return true;
    }
  }
  return false;
}

function play(board, col, player) {
  const next = board.map(row => [...row]);
  const row = landingRow(next, col);
  if (row < 0) return null;
  next[row][col] = player;
  return next;
}

function scoreWindow(values, player) {
  const opponent = player === "X" ? "O" : "X";
  const own = values.filter(v => v === player).length;
  const other = values.filter(v => v === opponent).length;
  const empty = values.filter(v => !v).length;
  if (own && other) return 0;
  if (own === 4) return 100000;
  if (other === 4) return -100000;
  if (own === 3 && empty === 1) return 120;
  if (own === 2 && empty === 2) return 12;
  if (other === 3 && empty === 1) return -150;
  if (other === 2 && empty === 2) return -14;
  return 0;
}

function evaluate(board, player) {
  let score = 0;
  for (let r = 0; r < ROWS; r++) {
    for (let c = 0; c <= COLS - 4; c++) score += scoreWindow([0,1,2,3].map(k => board[r][c+k]), player);
  }
  for (let c = 0; c < COLS; c++) {
    for (let r = 0; r <= ROWS - 4; r++) score += scoreWindow([0,1,2,3].map(k => board[r+k][c]), player);
  }
  for (let r = 0; r <= ROWS - 4; r++) for (let c = 0; c <= COLS - 4; c++) {
    score += scoreWindow([0,1,2,3].map(k => board[r+k][c+k]), player);
  }
  for (let r = 3; r < ROWS; r++) for (let c = 0; c <= COLS - 4; c++) {
    score += scoreWindow([0,1,2,3].map(k => board[r-k][c+k]), player);
  }
  for (let r = 0; r < ROWS; r++) if (board[r][3] === player) score += 6;
  return score;
}

function minimax(board, depth, alpha, beta, maximizing, player, opponent) {
  if (hasFour(board, player)) return 100000 + depth;
  if (hasFour(board, opponent)) return -100000 - depth;
  const valid = ORDER.filter(col => landingRow(board, col) >= 0);
  if (depth === 0 || !valid.length) return evaluate(board, player);
  if (maximizing) {
    let value = -Infinity;
    for (const col of valid) {
      value = Math.max(value, minimax(play(board, col, player), depth - 1, alpha, beta, false, player, opponent));
      alpha = Math.max(alpha, value);
      if (alpha >= beta) break;
    }
    return value;
  }
  let value = Infinity;
  for (const col of valid) {
    value = Math.min(value, minimax(play(board, col, opponent), depth - 1, alpha, beta, true, player, opponent));
    beta = Math.min(beta, value);
    if (alpha >= beta) break;
  }
  return value;
}

export function getConnectFourOutcome(input) {
  const board = normalizeBoard(input);
  if (hasFour(board, "X")) return "X";
  if (hasFour(board, "O")) return "O";
  return board.every(row => row.every(Boolean)) ? "draw" : "playing";
}

export function chooseConnectFourMove(input, { player = "X", depth = 4 } = {}) {
  const board = normalizeBoard(input);
  const own = String(player).toUpperCase();
  if (!["X", "O"].includes(own)) throw new TypeError("Player must be X or O.");
  if (!Number.isInteger(depth) || depth < 1 || depth > 6) throw new RangeError("Depth must be 1..6.");
  if (getConnectFourOutcome(board) !== "playing") return null;
  const opponent = own === "X" ? "O" : "X";
  let best = null, bestScore = -Infinity;
  for (const col of ORDER) {
    const next = play(board, col, own);
    if (!next) continue;
    const score = minimax(next, depth - 1, -Infinity, Infinity, false, own, opponent);
    if (score > bestScore) { bestScore = score; best = col; }
  }
  return best === null ? null : { type: "drop-column", column: best, index: (ROWS - 1) * COLS + best };
}
