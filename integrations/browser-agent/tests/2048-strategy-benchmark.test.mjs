import test from "node:test";
import assert from "node:assert/strict";
import {
  benchmark2048Strategies,
  create2048BenchmarkBoards
} from "../games/2048-strategy-benchmark.mjs";

test("creates reproducible valid 2048 benchmark positions from a seed", () => {
  const first = create2048BenchmarkBoards({ seed: 77, count: 5, occupied: 8 });
  const second = create2048BenchmarkBoards({ seed: 77, count: 5, occupied: 8 });
  assert.deepEqual(first, second);
  assert.equal(first.length, 5);
  for (const board of first) {
    assert.equal(board.length, 4);
    assert.equal(board.flat().filter(Boolean).length, 8);
    assert.ok(board.flat().every(value => value === 0 || (value >= 2 && (value & (value - 1)) === 0)));
  }
});

test("compares bounded 2048 search depths with reproducible aggregate metrics", () => {
  const boards = create2048BenchmarkBoards({ seed: 123, count: 4, occupied: 7 });
  const report = benchmark2048Strategies({ boards, depths: [1, 2] });
  assert.equal(report.results.length, 2);
  for (const result of report.results) {
    assert.equal(result.positions, 4);
    assert.equal(result.legalDecisions + result.terminalPositions, 4);
    assert.ok(Number.isFinite(result.immediateHeuristicMean));
    assert.ok(Number.isFinite(result.immediateHeuristicMedian));
    assert.equal(Object.values(result.directionCounts).reduce((sum, count) => sum + count, 0), result.legalDecisions);
  }
  assert.match(report.note, /not a win-rate/);
});

test("rejects unsafe benchmark sizes and unsupported depths", () => {
  assert.throws(() => create2048BenchmarkBoards({ count: 101 }), /count/);
  assert.throws(() => create2048BenchmarkBoards({ occupied: 15 }), /Occupied/);
  assert.throws(() => benchmark2048Strategies({ boards: [[[2]]], depths: [4] }), /depths/);
});
