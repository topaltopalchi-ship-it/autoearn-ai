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

function playEpisode({ seed, depth, maxMoves, evaluationOptions = {} }) {
  const random = makeRandom(seed);
  const board = Array.from({ length: 4 }, () => Array(4).fill(0));
  spawnTile(board, random);
  spawnTile(board, random);
  let score = 0;
  let moves = 0;
  let outcome = get2048Outcome(board);

  while (outcome === "playing" && moves < maxMoves) {
    const decision = choose2048Move(board, { depth, evaluationOptions });
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

export function compare2048HeuristicWeights({ seed = 2048, episodes = 10, depth = 2, maxMoves = 500, snakeWeight = 1 } = {}) {
  if (!Number.isInteger(seed) || seed < 0 || seed > 0xffffffff) throw new RangeError("Simulation seed must be an unsigned 32-bit integer.");
  if (!Number.isInteger(episodes) || episodes < 2 || episodes > 20) throw new RangeError("Heuristic comparison episodes must be 2..20.");
  if (!Number.isInteger(depth) || depth < 1 || depth > 3) throw new RangeError("Heuristic comparison depth must be 1..3.");
  if (!Number.isInteger(maxMoves) || maxMoves < 1 || maxMoves > 1000) throw new RangeError("Move limit must be 1..1000.");
  if (typeof snakeWeight !== "number" || !Number.isFinite(snakeWeight) || snakeWeight < 0 || snakeWeight > 2) throw new RangeError("Snake weight must be a number from 0 to 2.");
  const variants = [
    { label: "classic-no-snake", evaluationOptions: { snakeWeight: 0 } },
    { label: `snake-weight-${snakeWeight}`, evaluationOptions: { snakeWeight } }
  ];
  const seeds = Array.from({ length: episodes }, (_, index) => (seed + index * 0x9e3779b9) >>> 0);
  const results = variants.map(variant => ({
    variant: variant.label, depth, episodes,
    games: seeds.map(gameSeed => playEpisode({ seed: gameSeed, depth, maxMoves, evaluationOptions: variant.evaluationOptions }))
  }));
  const baseline = results[0].games;
  const candidate = results[1].games;
  const scoreDeltas = candidate.map((game, index) => game.score - baseline[index].score);
  const tileDeltas = candidate.map((game, index) => game.maxTile - baseline[index].maxTile);
  const wins = scoreDeltas.filter(delta => delta > 0).length;
  const losses = scoreDeltas.filter(delta => delta < 0).length;
  const tileWins = tileDeltas.filter(delta => delta > 0).length;
  const tileLosses = tileDeltas.filter(delta => delta < 0).length;
  const baselineWins = baseline.filter(game => game.outcome === "won").length;
  const candidateWins = candidate.filter(game => game.outcome === "won").length;
  return {
    seed, depth, episodes, maxMoves, snakeWeight, pairedSeeds: seeds,
    note: "Controlled local simulation: both heuristic variants receive identical deterministic seeds and search depth. Results are not real-site win rates or earnings evidence.",
    variants: results.map(item => ({
      variant: item.variant, averageScore: average(item.games.map(game => game.score)),
      medianScore: median(item.games.map(game => game.score)),
      averageMaxTile: average(item.games.map(game => game.maxTile)),
      reached2048: item.games.filter(game => game.outcome === "won").length,
      gameOvers: item.games.filter(game => game.outcome === "game_over").length,
      moveLimitStops: item.games.filter(game => game.moveLimitReached).length,
      averageMoves: average(item.games.map(game => game.moves))
    })),
    paired: {
      scoreWins: wins, scoreTies: scoreDeltas.length - wins - losses, scoreLosses: losses,
      maxTileWins: tileWins, maxTileTies: tileDeltas.length - tileWins - tileLosses, maxTileLosses: tileLosses,
      baseline2048Wins: baselineWins, candidate2048Wins: candidateWins,
      reached2048Delta: candidateWins - baselineWins,
      averageScoreDelta: average(scoreDeltas), medianScoreDelta: median(scoreDeltas),
      averageMaxTileDelta: average(tileDeltas),
      scoreDeltaBootstrap95: bootstrapMeanInterval(scoreDeltas, (seed ^ 0x9e3779b9) >>> 0)
    }
  };
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
