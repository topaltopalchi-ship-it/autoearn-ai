import { choose2048Move, get2048Outcome, move2048 } from "./2048-strategy.mjs";

function makeRandom(seed) {
  let state = seed >>> 0;
  return () => {
    state = (state * 1664525 + 1013904223) >>> 0;
    return state / 0x100000000;
  };
}

function spawnTile(board, random) {
  const empty = [];
  for (let y = 0; y < 4; y++) for (let x = 0; x < 4; x++) {
    if (board[y][x] === 0) empty.push([y, x]);
  }
  if (!empty.length) return false;
  const [y, x] = empty[Math.floor(random() * empty.length)];
  board[y][x] = random() < 0.9 ? 2 : 4;
  return true;
}

function playEpisode({ seed, depth, maxMoves }) {
  const random = makeRandom(seed);
  const board = Array.from({ length: 4 }, () => Array(4).fill(0));
  spawnTile(board, random);
  spawnTile(board, random);
  let score = 0;
  let moves = 0;
  let outcome = get2048Outcome(board);

  while (outcome === "playing" && moves < maxMoves) {
    const decision = choose2048Move(board, { depth });
    if (!decision) break;
    const result = move2048(board, decision.direction);
    if (!result.changed) throw new Error("Strategy returned a non-changing move.");
    for (let y = 0; y < 4; y++) for (let x = 0; x < 4; x++) board[y][x] = result.board[y][x];
    score += result.gained;
    moves++;
    outcome = get2048Outcome(board);
    if (outcome === "playing") spawnTile(board, random);
    outcome = get2048Outcome(board);
  }

  return {
    seed,
    depth,
    score,
    maxTile: Math.max(...board.flat()),
    moves,
    outcome,
    moveLimitReached: outcome === "playing" && moves >= maxMoves
  };
}

function average(values) {
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function median(values) {
  const sorted = [...values].sort((a, b) => a - b);
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
}


function percentile(sortedValues, probability) {
  if (!sortedValues.length) return null;
  const position = (sortedValues.length - 1) * probability;
  const lower = Math.floor(position);
  const upper = Math.ceil(position);
  if (lower === upper) return sortedValues[lower];
  return sortedValues[lower] + (sortedValues[upper] - sortedValues[lower]) * (position - lower);
}

function bootstrapMeanInterval(differences, seed, samples = 1000) {
  const random = makeRandom(seed);
  const means = [];
  for (let sample = 0; sample < samples; sample++) {
    let total = 0;
    for (let i = 0; i < differences.length; i++) {
      total += differences[Math.floor(random() * differences.length)];
    }
    means.push(total / differences.length);
  }
  means.sort((a, b) => a - b);
  return {
    lower95: percentile(means, 0.025),
    upper95: percentile(means, 0.975),
    samples
  };
}

function comparePairedEpisodes(comparisons, seed) {
  if (comparisons.length < 2) return [];
  const baseline = comparisons[0];
  return comparisons.slice(1).map((candidate, index) => {
    const scoreDifferences = candidate.games.map((game, i) => game.score - baseline.games[i].score);
    const tileDifferences = candidate.games.map((game, i) => game.maxTile - baseline.games[i].maxTile);
    const wins = scoreDifferences.filter(value => value > 0).length;
    const losses = scoreDifferences.filter(value => value < 0).length;
    const ties = scoreDifferences.length - wins - losses;
    const interval = bootstrapMeanInterval(scoreDifferences, (seed + (index + 1) * 0x85ebca6b) >>> 0);
    return {
      baselineDepth: baseline.depth,
      candidateDepth: candidate.depth,
      episodes: scoreDifferences.length,
      scoreWins: wins,
      scoreTies: ties,
      scoreLosses: losses,
      averagePairedScoreDelta: average(scoreDifferences),
      medianPairedScoreDelta: median(scoreDifferences),
      averagePairedMaxTileDelta: average(tileDifferences),
      scoreDeltaBootstrap95: interval
    };
  });
}

export function simulate2048Episodes({
  seed = 2048,
  episodes = 5,
  depths = [1, 2, 3],
  maxMoves = 500
} = {}) {
  if (!Number.isInteger(seed) || seed < 0 || seed > 0xffffffff) {
    throw new RangeError("Simulation seed must be an unsigned 32-bit integer.");
  }
  if (!Number.isInteger(episodes) || episodes < 1 || episodes > 20) {
    throw new RangeError("Episode count must be 1..20.");
  }
  if (!Number.isInteger(maxMoves) || maxMoves < 1 || maxMoves > 1000) {
    throw new RangeError("Move limit must be 1..1000.");
  }
  if (!Array.isArray(depths) || depths.length < 1 ||
      depths.some(depth => !Number.isInteger(depth) || depth < 1 || depth > 3)) {
    throw new RangeError("Simulation depths must be integers from 1 to 3.");
  }

  const comparisons = depths.map(depth => {
    const games = Array.from({ length: episodes }, (_, index) =>
      playEpisode({ seed: (seed + index * 0x9e3779b9) >>> 0, depth, maxMoves }));
    const scores = games.map(game => game.score);
    const maxTiles = games.map(game => game.maxTile);
    return {
      depth,
      episodes,
      averageScore: average(scores),
      medianScore: median(scores),
      averageMaxTile: average(maxTiles),
      highestTile: Math.max(...maxTiles),
      reached2048: games.filter(game => game.outcome === "won").length,
      gameOvers: games.filter(game => game.outcome === "game_over").length,
      moveLimitStops: games.filter(game => game.moveLimitReached).length,
      averageMoves: average(games.map(game => game.moves)),
      games
    };
  });

  return {
    seed,
    note: "Seeded local simulations only. These are not real-site win rates, guarantees, or evidence of earnings.",
    comparisons,
    pairedComparisons: comparePairedEpisodes(comparisons, seed)
  };
}
