import { choose2048Move, evaluate2048Board, get2048Outcome, move2048 } from "./2048-strategy.mjs";

function createRandom(seed) {
  let state = seed >>> 0;
  return () => {
    state = (state * 1664525 + 1013904223) >>> 0;
    return state / 0x100000000;
  };
}

export function create2048BenchmarkBoards({ seed = 2048, count = 12, occupied = 8 } = {}) {
  if (!Number.isInteger(seed) || seed < 0 || seed > 0xffffffff) {
    throw new RangeError("Benchmark seed must be an unsigned 32-bit integer.");
  }
  if (!Number.isInteger(count) || count < 1 || count > 100) {
    throw new RangeError("Benchmark count must be 1..100.");
  }
  if (!Number.isInteger(occupied) || occupied < 2 || occupied > 14) {
    throw new RangeError("Occupied cells must be 2..14.");
  }
  const random = createRandom(seed);
  return Array.from({ length: count }, () => {
    const cells = Array(16).fill(0);
    const positions = Array.from({ length: 16 }, (_, index) => index);
    for (let i = positions.length - 1; i > 0; i--) {
      const j = Math.floor(random() * (i + 1));
      [positions[i], positions[j]] = [positions[j], positions[i]];
    }
    for (const index of positions.slice(0, occupied)) {
      const exponent = random() < 0.82 ? 1 + Math.floor(random() * 5) : 6 + Math.floor(random() * 3);
      cells[index] = 2 ** exponent;
    }
    return Array.from({ length: 4 }, (_, row) => cells.slice(row * 4, row * 4 + 4));
  });
}

function median(values) {
  const sorted = [...values].sort((a, b) => a - b);
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
}

export function benchmark2048Strategies({ boards = null, seed = 2048, count = 12, occupied = 8, depths = [1, 2, 3] } = {}) {
  const positions = boards ?? create2048BenchmarkBoards({ seed, count, occupied });
  if (!Array.isArray(positions) || positions.length < 1 || positions.length > 100) {
    throw new TypeError("Benchmark requires 1..100 boards.");
  }
  if (!Array.isArray(depths) || depths.length < 1 ||
      depths.some(depth => !Number.isInteger(depth) || depth < 1 || depth > 3)) {
    throw new RangeError("Benchmark depths must be integers from 1 to 3.");
  }
  const results = depths.map(depth => {
    const decisions = positions.map(board => {
      const decision = choose2048Move(board, { depth });
      if (!decision) return { terminal: true, score: evaluate2048Board(board), key: null, searchScore: null };
      const moved = move2048(board, decision.direction);
      return {
        terminal: false,
        score: evaluate2048Board(moved.board),
        searchScore: decision.score,
        key: decision.key,
        won: get2048Outcome(moved.board) === "won"
      };
    });
    const scores = decisions.map(item => item.score);
    const searchScores = decisions.filter(item => Number.isFinite(item.searchScore)).map(item => item.searchScore);
    const directionCounts = Object.fromEntries(["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"]
      .map(key => [key, decisions.filter(item => item.key === key).length]));
    return {
      depth,
      positions: positions.length,
      legalDecisions: decisions.filter(item => !item.terminal).length,
      terminalPositions: decisions.filter(item => item.terminal).length,
      immediateHeuristicMean: scores.reduce((sum, value) => sum + value, 0) / scores.length,
      immediateHeuristicMedian: median(scores),
      expectedSearchValueMean: searchScores.length
        ? searchScores.reduce((sum, value) => sum + value, 0) / searchScores.length
        : null,
      predictedWinningBoards: decisions.filter(item => item.won).length,
      directionCounts
    };
  });
  return {
    seed: boards ? null : seed,
    note: "Synthetic deterministic benchmark only; heuristic and search values are not measured win rates or real-game results.",
    results
  };
}
