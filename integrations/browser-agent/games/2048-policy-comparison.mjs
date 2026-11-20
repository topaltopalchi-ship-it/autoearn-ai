import { choose2048Move, choose2048MoveAdaptive, get2048Outcome, move2048 } from "./2048-strategy.mjs";

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

function playPolicy({ seed, policy, maxMoves, maxNodes }) {
  const random = makeRandom(seed);
  const board = Array.from({ length: 4 }, () => Array(4).fill(0));
  spawnTile(board, random);
  spawnTile(board, random);
  let score = 0;
  let moves = 0;
  let outcome = get2048Outcome(board);
  const depthCounts = { 1: 0, 2: 0, 3: 0 };
  const searchStats = { nodesVisited: 0, cacheHits: 0, budgetExhaustedMoves: 0 };

  while (outcome === "playing" && moves < maxMoves) {
    const decision = policy.kind === "adaptive"
      ? choose2048MoveAdaptive(board, { maxNodes })
      : choose2048Move(board, { depth: policy.depth, maxNodes });
    if (!decision) break;
    if (decision.searchDepth) depthCounts[decision.searchDepth]++;
    else depthCounts[policy.depth]++;
    if (decision.searchStats) {
      searchStats.nodesVisited += decision.searchStats.nodesVisited;
      searchStats.cacheHits += decision.searchStats.cacheHits;
      if (decision.searchStats.budgetExhausted) searchStats.budgetExhaustedMoves++;
    }
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
    seed, policy: policy.label, score, maxTile: Math.max(...board.flat()),
    moves, outcome, moveLimitReached: outcome === "playing" && moves >= maxMoves,
    depthCounts, searchStats,
    averageSearchNodesPerMove: moves ? searchStats.nodesVisited / moves : 0
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

function summarize(policy, games) {
  const scores = games.map(game => game.score);
  const maxTiles = games.map(game => game.maxTile);
  const depthCounts = { 1: 0, 2: 0, 3: 0 };
  const searchStats = { nodesVisited: 0, cacheHits: 0, budgetExhaustedMoves: 0 };
  for (const game of games) {
    for (const depth of [1, 2, 3]) depthCounts[depth] += game.depthCounts[depth];
    for (const key of Object.keys(searchStats)) searchStats[key] += game.searchStats[key];
  }
  return {
    policy, episodes: games.length, averageScore: average(scores), medianScore: median(scores),
    averageMaxTile: average(maxTiles), highestTile: Math.max(...maxTiles),
    reached2048: games.filter(game => game.outcome === "won").length,
    gameOvers: games.filter(game => game.outcome === "game_over").length,
    moveLimitStops: games.filter(game => game.moveLimitReached).length,
    averageMoves: average(games.map(game => game.moves)), depthCounts, searchStats,
    averageSearchNodesPerMove: searchStats.nodesVisited / Math.max(1, games.reduce((sum, game) => sum + game.moves, 0)),
    games
  };
}

export function compare2048Policies({ seed = 2048, episodes = 5, maxMoves = 500, maxNodes = 250 } = {}) {
  if (!Number.isInteger(seed) || seed < 0 || seed > 0xffffffff) {
    throw new RangeError("Comparison seed must be an unsigned 32-bit integer.");
  }
  if (!Number.isInteger(episodes) || episodes < 1 || episodes > 20) {
    throw new RangeError("Episode count must be 1..20.");
  }
  if (!Number.isInteger(maxMoves) || maxMoves < 1 || maxMoves > 1000) {
    throw new RangeError("Move limit must be 1..1000.");
  }
  if (!Number.isInteger(maxNodes) || maxNodes < 100 || maxNodes > 200000) {
    throw new RangeError("Search node budget must be 100..200000.");
  }

  const policies = [
    { kind: "fixed", depth: 1, label: "fixed-depth-1" },
    { kind: "fixed", depth: 2, label: "fixed-depth-2" },
    { kind: "fixed", depth: 3, label: "fixed-depth-3" },
    { kind: "adaptive", label: "adaptive" }
  ];
  const seeds = Array.from({ length: episodes }, (_, index) => (seed + index * 0x9e3779b9) >>> 0);
  const summaries = policies.map(policy => summarize(
    policy.label,
    seeds.map(gameSeed => playPolicy({ seed: gameSeed, policy, maxMoves, maxNodes }))
  ));
  const fixedPolicies = summaries.filter(item => item.policy.startsWith("fixed-depth-"));
  const pairedComparisons = summaries.flatMap(item => fixedPolicies.map(baseline => {
    const pairs = item.games.map((game, index) => ({
      seed: game.seed,
      scoreDifference: game.score - baseline.games[index].score,
      maxTileDifference: game.maxTile - baseline.games[index].maxTile,
      searchNodesDifference: game.searchStats.nodesVisited - baseline.games[index].searchStats.nodesVisited,
      cacheHitsDifference: game.searchStats.cacheHits - baseline.games[index].searchStats.cacheHits,
      budgetExhaustionDifference: game.searchStats.budgetExhaustedMoves - baseline.games[index].searchStats.budgetExhaustedMoves
    }));
    return {
      policy: item.policy,
      comparedWith: baseline.policy,
      averagePairedScoreDifference: average(pairs.map(pair => pair.scoreDifference)),
      medianPairedScoreDifference: median(pairs.map(pair => pair.scoreDifference)),
      minPairedScoreDifference: Math.min(...pairs.map(pair => pair.scoreDifference)),
      maxPairedScoreDifference: Math.max(...pairs.map(pair => pair.scoreDifference)),
      averageAbsolutePairedScoreDifference: average(pairs.map(pair => Math.abs(pair.scoreDifference))),
      averagePairedSearchNodesDifference: average(pairs.map(pair => pair.searchNodesDifference)),
      medianPairedSearchNodesDifference: median(pairs.map(pair => pair.searchNodesDifference)),
      averagePairedCacheHitsDifference: average(pairs.map(pair => pair.cacheHitsDifference)),
      averagePairedBudgetExhaustionDifference: average(pairs.map(pair => pair.budgetExhaustionDifference)),
      scoreWins: pairs.filter(pair => pair.scoreDifference > 0).length,
      scoreTies: pairs.filter(pair => pair.scoreDifference === 0).length,
      scoreLosses: pairs.filter(pair => pair.scoreDifference < 0).length,
      maxTileWins: pairs.filter(pair => pair.maxTileDifference > 0).length,
      maxTileTies: pairs.filter(pair => pair.maxTileDifference === 0).length,
      maxTileLosses: pairs.filter(pair => pair.maxTileDifference < 0).length,
      pairs
    };
  }));

  return {
    seed, episodes, maxMoves, maxNodes, seeds,
    note: "Paired seeded local simulations only. Shared seeds improve reproducibility but do not establish real-site win rates, guarantees, or earnings.",
    summaries, pairedComparisons
  };
}
