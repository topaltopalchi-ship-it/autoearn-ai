const SIZE = 4;
const MOVES = [
  { key: "ArrowLeft", direction: "left" },
  { key: "ArrowUp", direction: "up" },
  { key: "ArrowRight", direction: "right" },
  { key: "ArrowDown", direction: "down" }
];

function validateBoard(board) {
  if (!Array.isArray(board) || board.length !== SIZE ||
      board.some(row => !Array.isArray(row) || row.length !== SIZE ||
        row.some(value => !Number.isInteger(value) || value < 0 ||
          (value !== 0 && (value & (value - 1)) !== 0)))) {
    throw new TypeError("A 4x4 board of zeroes and positive powers of two is required.");
  }
}

function mergeLine(line) {
  const values = line.filter(value => value !== 0);
  const output = [];
  let gained = 0;
  for (let i = 0; i < values.length; i++) {
    if (values[i] === values[i + 1]) {
      const merged = values[i] * 2;
      output.push(merged);
      gained += merged;
      i++;
    } else {
      output.push(values[i]);
    }
  }
  while (output.length < SIZE) output.push(0);
  return { line: output, gained };
}

export function move2048(board, direction) {
  validateBoard(board);
  if (!["left", "right", "up", "down"].includes(direction)) {
    throw new TypeError("Unsupported 2048 direction.");
  }
  const next = Array.from({ length: SIZE }, () => Array(SIZE).fill(0));
  let gained = 0;
  for (let index = 0; index < SIZE; index++) {
    let line = direction === "left" || direction === "right"
      ? [...board[index]]
      : board.map(row => row[index]);
    if (direction === "right" || direction === "down") line.reverse();
    const merged = mergeLine(line);
    gained += merged.gained;
    line = merged.line;
    if (direction === "right" || direction === "down") line.reverse();
    for (let offset = 0; offset < SIZE; offset++) {
      if (direction === "left" || direction === "right") next[index][offset] = line[offset];
      else next[offset][index] = line[offset];
    }
  }
  return { board: next, gained, changed: next.some((row, y) => row.some((value, x) => value !== board[y][x])) };
}

function logTile(value) {
  return value === 0 ? 0 : Math.log2(value);
}

export function evaluate2048Board(board) {
  validateBoard(board);
  const empty = board.flat().filter(value => value === 0).length;
  const values = board.map(row => row.map(logTile));
  let smoothness = 0;
  let monotonicity = 0;
  for (let y = 0; y < SIZE; y++) {
    let increasing = 0, decreasing = 0;
    for (let x = 0; x < SIZE - 1; x++) {
      const diff = values[y][x] - values[y][x + 1];
      smoothness -= Math.abs(diff);
      if (diff > 0) decreasing -= diff;
      else increasing += diff;
    }
    monotonicity += Math.max(increasing, decreasing);
  }
  for (let x = 0; x < SIZE; x++) {
    let increasing = 0, decreasing = 0;
    for (let y = 0; y < SIZE - 1; y++) {
      const diff = values[y][x] - values[y + 1][x];
      if (diff > 0) decreasing -= diff;
      else increasing += diff;
    }
    monotonicity += Math.max(increasing, decreasing);
  }
  const maximum = Math.max(...board.flat());
  const corners = [board[0][0], board[0][3], board[3][0], board[3][3]];
  const cornerBonus = corners.includes(maximum) ? logTile(maximum) * 18 : 0;
  return empty * 270 + smoothness * 11 + monotonicity * 45 + cornerBonus;
}

export function choose2048Move(board) {
  validateBoard(board);
  let best = null;
  for (const move of MOVES) {
    const result = move2048(board, move.direction);
    if (!result.changed) continue;
    const score = evaluate2048Board(result.board) + result.gained * 0.08;
    if (!best || score > best.score) {
      best = { type: "press", key: move.key, direction: move.direction, score, expectedBoard: result.board };
    }
  }
  return best;
}

export function create2048Decision() {
  return async observation => {
    if (!observation || !Array.isArray(observation.board)) return null;
    const move = choose2048Move(observation.board);
    return move ? { type: move.type, key: move.key, direction: move.direction } : null;
  };
}
