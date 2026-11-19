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
