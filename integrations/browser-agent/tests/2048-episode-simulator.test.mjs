import test from "node:test";
import assert from "node:assert/strict";
import { simulate2048Episodes } from "../games/2048-episode-simulator.mjs";

test("runs reproducible complete 2048 episodes for multiple search depths", () => {
  const options = { seed: 91, episodes: 2, depths: [1, 2], maxMoves: 80 };
  const first = simulate2048Episodes(options);
  const second = simulate2048Episodes(options);
  assert.deepEqual(first, second);
  assert.equal(first.comparisons.length, 2);
  for (const comparison of first.comparisons) {
    assert.equal(comparison.games.length, 2);
    assert.ok(Number.isFinite(comparison.averageScore));
    assert.ok(Number.isFinite(comparison.averageMaxTile));
    assert.ok(comparison.games.every(game => game.moves <= 80));
    assert.ok(comparison.games.every(game => ["won", "game_over", "playing"].includes(game.outcome)));
  }
  assert.match(first.note, /not real-site win rates/);
  assert.deepEqual(first.pairedComparisons, second.pairedComparisons);
  assert.equal(first.pairedComparisons.length, 1);
  const paired = first.pairedComparisons[0];
  assert.equal(paired.baselineDepth, 1);
  assert.equal(paired.candidateDepth, 2);
  assert.equal(paired.scoreWins + paired.scoreTies + paired.scoreLosses, 2);
  assert.ok(Number.isFinite(paired.averagePairedScoreDelta));
  assert.ok(paired.scoreDeltaBootstrap95.lower95 <= paired.scoreDeltaBootstrap95.upper95);
  assert.equal(paired.scoreDeltaBootstrap95.samples, 1000);
});

test("reports explicit move-limit stops instead of calling them losses", () => {
  const report = simulate2048Episodes({ seed: 5, episodes: 1, depths: [1], maxMoves: 1 });
  const game = report.comparisons[0].games[0];
  assert.equal(game.moves, 1);
  assert.equal(game.moveLimitReached, game.outcome === "playing");
});

test("rejects unbounded or invalid simulation settings", () => {
  assert.throws(() => simulate2048Episodes({ episodes: 21 }), /Episode count/);
  assert.throws(() => simulate2048Episodes({ maxMoves: 1001 }), /Move limit/);
  assert.throws(() => simulate2048Episodes({ depths: [4] }), /depths/);
});

test("compares classic and snake heuristics on identical deterministic episodes", async () => {
  const { compare2048HeuristicWeights } = await import("../games/2048-episode-simulator.mjs");
  const options = { seed: 1234, episodes: 2, depth: 1, maxMoves: 60 };
  const first = compare2048HeuristicWeights(options);
  const second = compare2048HeuristicWeights(options);
  assert.deepEqual(first, second);
  assert.equal(first.variants.length, 2);
  assert.equal(first.variants[0].variant, "classic-no-snake");
  assert.equal(first.variants[1].variant, "snake-weight-1");
  assert.equal(first.paired.scoreWins + first.paired.scoreTies + first.paired.scoreLosses, 2);
  assert.equal(first.paired.maxTileWins + first.paired.maxTileTies + first.paired.maxTileLosses, 2);
  assert.equal(first.paired.baseline2048Wins, first.variants[0].reached2048);
  assert.equal(first.paired.candidate2048Wins, first.variants[1].reached2048);
  assert.equal(first.paired.reached2048Delta, first.variants[1].reached2048 - first.variants[0].reached2048);
  for (const variant of first.variants) {
    assert.equal(variant.moveLimitStops + variant.gameOvers + variant.reached2048, 2);
    assert.ok(variant.moveLimitStops >= 0 && variant.moveLimitStops <= 2);
  }
  assert.ok(Number.isFinite(first.paired.averageScoreDelta));
  assert.ok(first.paired.scoreDeltaBootstrap95.lower95 <= first.paired.scoreDeltaBootstrap95.upper95);
});

test("requires enough paired games for heuristic comparison", async () => {
  const { compare2048HeuristicWeights } = await import("../games/2048-episode-simulator.mjs");
  assert.throws(() => compare2048HeuristicWeights({ episodes: 1 }), /episodes/);
});