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

function legalMoves(board) {
  return MOVES.map(move => ({ ...move, result: move2048(board, move.direction) }))
    .filter(move => move.result.changed);
}

function consumeSearchNode(budget) {
  if (budget.nodesVisited >= budget.maxNodes) {
    budget.budgetExhausted = true;
    return false;
  }
  budget.nodesVisited++;
  return true;
}

function expectimaxMax(board, depth, cache, budget) {
  if (depth <= 0) return evaluate2048Board(board);
  const key = `M${depth}:${board.flat().join(",")}`;
  if (cache.has(key)) {
    budget.cacheHits++;
    return cache.get(key);
  }
  if (!consumeSearchNode(budget)) return evaluate2048Board(board);
  const moves = legalMoves(board);
  if (!moves.length) return evaluate2048Board(board);
  let best = -Infinity;
  for (const move of moves) {
    const score = move.result.gained * 0.08 +
      expectimaxChance(move.result.board, depth - 1, cache, budget);
    if (score > best) best = score;
  }
  cache.set(key, best);
  return best;
}

function expectimaxChance(board, depth, cache, budget) {
  if (depth <= 0) return evaluate2048Board(board);
  const key = `C${depth}:${board.flat().join(",")}`;
  if (cache.has(key)) {
    budget.cacheHits++;
    return cache.get(key);
  }
  if (!consumeSearchNode(budget)) return evaluate2048Board(board);
  const empty = [];
  for (let y = 0; y < SIZE; y++) {
    for (let x = 0; x < SIZE; x++) {
      if (board[y][x] === 0) empty.push([y, x]);
    }
  }
  if (!empty.length) return expectimaxMax(board, depth, cache, budget);
  let expected = 0;
  for (const [y, x] of empty) {
    const withTwo = board.map(row => [...row]);
    withTwo[y][x] = 2;
    const withFour = board.map(row => [...row]);
    withFour[y][x] = 4;
    expected += 0.9 * expectimaxMax(withTwo, depth, cache, budget) +
      0.1 * expectimaxMax(withFour, depth, cache, budget);
  }
  const score = expected / empty.length;
  cache.set(key, score);
  return score;
}

export function choose2048Move(board, { depth = 3, maxNodes = 25000 } = {}) {
  validateBoard(board);
  if (!Number.isInteger(depth) || depth < 1 || depth > 4) {
    throw new RangeError("2048 search depth must be an integer from 1 to 4.");
  }
  if (!Number.isInteger(maxNodes) || maxNodes < 1 || maxNodes > 200000) {
    throw new RangeError("2048 maxNodes must be an integer from 1 to 200000.");
  }
  const moves = legalMoves(board);
  if (!moves.length) return null;
  const perMoveNodeBudget = Math.max(1, Math.floor(maxNodes / moves.length));
  const aggregateStats = { nodesVisited: 0, cacheHits: 0, budgetExhausted: false };
  let best = null;
  for (const move of moves) {
    // Give every legal root action its own equal budget so early directions
    // cannot consume the search allowance and bias later alternatives.
    const cache = new Map();
    const budget = {
      maxNodes: perMoveNodeBudget,
      nodesVisited: 0,
      cacheHits: 0,
      budgetExhausted: false
    };
    const score = move.result.gained * 0.08 +
      expectimaxChance(move.result.board, depth - 1, cache, budget);
    aggregateStats.nodesVisited += budget.nodesVisited;
    aggregateStats.cacheHits += budget.cacheHits;
    aggregateStats.budgetExhausted ||= budget.budgetExhausted;
    if (!best || score > best.score) {
      best = {
        type: "press",
        key: move.key,
        direction: move.direction,
        score,
        expectedBoard: move.result.board
      };
    }
  }
  best.searchStats = {
    ...aggregateStats,
    maxNodes,
    perMoveNodeBudget,
    rootMovesEvaluated: moves.length
  };
  return best;
}

export function analyze2048Position(board) {
  validateBoard(board);
  const values = board.flat();
  const emptyCells = values.filter(value => value === 0).length;
  return {
    emptyCells,
    occupiedCells: 16 - emptyCells,
    highestTile: Math.max(...values),
    legalMoves: legalMoves(board).length
  };
}

export function select2048SearchDepth(board, { minDepth = 1, maxDepth = 3 } = {}) {
  if (!Number.isInteger(minDepth) || !Number.isInteger(maxDepth) ||
      minDepth < 1 || maxDepth > 4 || minDepth > maxDepth) {
    throw new RangeError("Adaptive depth bounds must satisfy 1 <= minDepth <= maxDepth <= 4.");
  }
  const metrics = analyze2048Position(board);
  if (metrics.legalMoves === 0) return minDepth;
  const suggested = metrics.emptyCells >= 10 ? 1 : metrics.emptyCells >= 6 ? 2 : 3;
  return Math.max(minDepth, Math.min(maxDepth, suggested));
}

export function choose2048MoveAdaptive(board, options = {}) {
  const { minDepth, maxDepth, maxNodes = 25000 } = options;
  const depth = select2048SearchDepth(board, { minDepth, maxDepth });
  const move = choose2048Move(board, { depth, maxNodes });
  return move ? { ...move, searchDepth: depth, position: analyze2048Position(board) } : null;
}

export function create2048Decision({ depth = 3 } = {}) {
  return async observation => {
    if (!observation || !Array.isArray(observation.board)) return null;
    const move = choose2048Move(observation.board, { depth });
    return move ? { type: move.type, key: move.key, direction: move.direction } : null;
  };
}

export function createAdaptive2048Decision(options = {}) {
  return async observation => {
    if (!observation || !Array.isArray(observation.board)) return null;
    const move = choose2048MoveAdaptive(observation.board, options);
    return move ? { type: move.type, key: move.key, direction: move.direction } : null;
  };
}

export function get2048Outcome(board) {
  validateBoard(board);
  if (Math.max(...board.flat()) >= 2048) return "won";
  if (legalMoves(board).length === 0) return "game_over";
  return "playing";
}
