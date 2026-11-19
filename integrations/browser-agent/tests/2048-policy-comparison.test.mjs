import test from "node:test";
import assert from "node:assert/strict";
import { compare2048Policies } from "../games/2048-policy-comparison.mjs";

test("compares fixed and adaptive policies on identical reproducible seeds", () => {
  const options = { seed: 71, episodes: 2, maxMoves: 60 };
  const first = compare2048Policies(options);
  const second = compare2048Policies(options);
  assert.deepEqual(first, second);
  assert.deepEqual(first.summaries.map(item => item.policy), [
    "fixed-depth-1", "fixed-depth-2", "fixed-depth-3", "adaptive"
  ]);
  assert.equal(first.summaries[0].games[0].seed, first.summaries[3].games[0].seed);
  assert.equal(first.pairedComparisons.length, 12);
  const adaptiveComparisons = first.pairedComparisons.filter(item => item.policy === "adaptive");
  assert.equal(adaptiveComparisons.length, 3);
  assert.deepEqual(adaptiveComparisons.map(item => item.comparedWith), [
    "fixed-depth-1", "fixed-depth-2", "fixed-depth-3"
  ]);
  assert.ok(adaptiveComparisons.every(item =>
    item.scoreWins + item.scoreTies + item.scoreLosses === 2 &&
    item.maxTileWins + item.maxTileTies + item.maxTileLosses === 2
  ));
  assert.ok(first.summaries[3].depthCounts[1] + first.summaries[3].depthCounts[2] +
    first.summaries[3].depthCounts[3] > 0);
  for (const summary of first.summaries) {
    assert.ok(Number.isFinite(summary.averageSearchNodesPerMove));
    assert.ok(summary.searchStats.nodesVisited >= 0);
    assert.ok(summary.searchStats.cacheHits >= 0);
    assert.ok(summary.searchStats.budgetExhaustedMoves >= 0);
  }
  assert.match(first.note, /do not establish real-site win rates/);
});

test("reports paired score wins, ties, and losses without treating move caps as losses", () => {
  const report = compare2048Policies({ seed: 5, episodes: 1, maxMoves: 1 });
  const pair = report.pairedComparisons.find(item =>
    item.policy === "adaptive" && item.comparedWith === "fixed-depth-3"
  );
  assert.equal(pair.pairs.length, 1);
  assert.equal(pair.scoreWins + pair.scoreTies + pair.scoreLosses, 1);
  assert.ok(report.summaries.every(item => item.moveLimitStops <= 1));
});

test("rejects unsafe comparison bounds", () => {
  assert.throws(() => compare2048Policies({ episodes: 21 }), /Episode count/);
  assert.throws(() => compare2048Policies({ maxMoves: 1001 }), /Move limit/);
  assert.throws(() => compare2048Policies({ seed: -1 }), /seed/);
});
