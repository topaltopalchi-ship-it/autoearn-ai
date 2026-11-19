import test from "node:test";
import assert from "node:assert/strict";
import { choose2048Move, evaluate2048Board, move2048 } from "../games/2048-strategy.mjs";

test("merges each pair once and reports gained score", () => {
  const board = [
    [2, 2, 2, 2],
    [0, 0, 0, 0],
    [0, 0, 0, 0],
    [0, 0, 0, 0]
  ];
  const result = move2048(board, "left");
  assert.deepEqual(result.board[0], [4, 4, 0, 0]);
  assert.equal(result.gained, 8);
  assert.equal(result.changed, true);
});

test("does not treat a no-op as a legal move", () => {
  const board = [
    [2, 4, 8, 16],
    [4, 8, 16, 32],
    [8, 16, 32, 64],
    [16, 32, 64, 128]
  ];
  assert.equal(choose2048Move(board), null);
});

test("selects only a legal arrow-key move", () => {
  const board = [
    [2, 0, 0, 0],
    [0, 0, 0, 0],
    [0, 0, 0, 0],
    [0, 0, 0, 0]
  ];
  const move = choose2048Move(board);
  assert.ok(["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"].includes(move.key));
  assert.equal(move.type, "press");
  assert.ok(move.expectedBoard.flat().includes(2));
});

test("expectimax evaluates future random tile spawns and returns a legal move", () => {
  const board = [
    [2, 4, 8, 16],
    [0, 0, 0, 0],
    [0, 0, 0, 0],
    [0, 0, 0, 0]
  ];
  const shallow = choose2048Move(board, { depth: 1 });
  const lookahead = choose2048Move(board, { depth: 3 });
  for (const move of [shallow, lookahead]) {
    assert.ok(move);
    assert.ok(["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"].includes(move.key));
    assert.equal(move.expectedBoard.length, 4);
  }
});

test("rejects unsupported expectimax search depths", () => {
  const board = Array.from({ length: 4 }, () => [0, 0, 0, 0]);
  assert.throws(() => choose2048Move(board, { depth: 0 }), /search depth/);
  assert.throws(() => choose2048Move(board, { depth: 5 }), /search depth/);
});

test("prefers boards with more empty cells", () => {
  const sparse = [
    [2, 0, 0, 0],
    [0, 0, 0, 0],
    [0, 0, 0, 0],
    [0, 0, 0, 0]
  ];
  const crowded = [
    [2, 4, 8, 16],
    [4, 8, 16, 32],
    [8, 16, 32, 64],
    [16, 32, 64, 128]
  ];
  assert.ok(evaluate2048Board(sparse) > evaluate2048Board(crowded));
});

test("rejects malformed boards and directions", () => {
  assert.throws(() => choose2048Move([[2, 2]]), /4x4 board/);
  assert.throws(() => move2048(Array.from({length:4}, () => [0,0,0,0]), "diagonal"), /direction/);
});

test("recognizes a 2048 win and a no-moves game over", async () => {
  const { get2048Outcome } = await import("../games/2048-strategy.mjs");
  assert.equal(get2048Outcome([
    [2048, 0, 0, 0],
    [0, 0, 0, 0],
    [0, 0, 0, 0],
    [0, 0, 0, 0]
  ]), "won");
  assert.equal(get2048Outcome([
    [2, 4, 8, 16],
    [4, 8, 16, 32],
    [8, 16, 32, 64],
    [16, 32, 64, 128]
  ]), "game_over");
});


test("adaptive search depth increases as the board becomes crowded", async () => {
  const { select2048SearchDepth, analyze2048Position, choose2048MoveAdaptive } =
    await import("../games/2048-strategy.mjs");
  const openBoard = [
    [2, 0, 0, 0],
    [0, 0, 0, 0],
    [0, 0, 0, 0],
    [0, 0, 0, 0]
  ];
  const mediumBoard = [
    [2, 4, 8, 16],
    [4, 8, 16, 0],
    [8, 16, 0, 0],
    [16, 0, 0, 0]
  ];
  const crowdedBoard = [
    [2, 4, 8, 16],
    [4, 8, 16, 32],
    [8, 16, 32, 64],
    [16, 32, 64, 0]
  ];
  assert.equal(analyze2048Position(openBoard).emptyCells, 15);
  assert.equal(select2048SearchDepth(openBoard), 1);
  assert.equal(select2048SearchDepth(mediumBoard), 2);
  assert.equal(select2048SearchDepth(crowdedBoard), 3);
  const decision = choose2048MoveAdaptive(crowdedBoard);
  assert.equal(decision.searchDepth, 3);
  assert.ok(["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"].includes(decision.key));
});

test("adaptive search respects configured depth bounds and rejects invalid bounds", async () => {
  const { select2048SearchDepth } = await import("../games/2048-strategy.mjs");
  const board = Array.from({ length: 4 }, () => [0, 0, 0, 0]);
  assert.equal(select2048SearchDepth(board, { minDepth: 2, maxDepth: 2 }), 2);
  assert.throws(() => select2048SearchDepth(board, { minDepth: 3, maxDepth: 2 }), /bounds/);
  assert.throws(() => select2048SearchDepth(board, { minDepth: 0, maxDepth: 2 }), /bounds/);
});


test("bounds expectimax work and reports when its node budget is exhausted", () => {
  const board = [
    [2, 4, 8, 16],
    [4, 8, 16, 32],
    [8, 16, 32, 64],
    [16, 32, 64, 0]
  ];
  const move = choose2048Move(board, { depth: 4, maxNodes: 1 });
  assert.ok(move);
  assert.equal(move.searchStats.maxNodes, 1);
  assert.ok(move.searchStats.nodesVisited <= 1);
  assert.equal(move.searchStats.perMoveNodeBudget, 0);
  assert.ok(move.searchStats.rootMovesEvaluated >= 1);
  assert.equal(move.searchStats.budgetExhausted, true);
  assert.ok(move.searchStats.cacheHits >= 0);
});

test("rejects an invalid expectimax node budget", () => {
  const board = Array.from({ length: 4 }, () => [0, 0, 0, 0]);
  assert.throws(() => choose2048Move(board, { maxNodes: 0 }), /maxNodes/);
  assert.throws(() => choose2048Move(board, { maxNodes: 200001 }), /maxNodes/);
});


test("adaptive strategy forwards a caller's bounded node budget", async () => {
  const { choose2048MoveAdaptive } = await import("../games/2048-strategy.mjs");
  const board = [
    [2, 4, 8, 16],
    [4, 8, 16, 32],
    [8, 16, 32, 64],
    [16, 32, 64, 0]
  ];
  const move = choose2048MoveAdaptive(board, { maxNodes: 1 });
  assert.ok(move);
  assert.equal(move.searchStats.maxNodes, 1);
  assert.equal(move.searchStats.budgetExhausted, true);
});


test("shares the node allowance fairly across all legal root moves", () => {
  const board = [
    [2, 4, 8, 16],
    [4, 8, 16, 32],
    [8, 16, 32, 64],
    [16, 32, 64, 0]
  ];
  const move = choose2048Move(board, { depth: 4, maxNodes: 100 });
  assert.ok(move);
  assert.equal(move.searchStats.perMoveNodeBudget,
    Math.floor(100 / move.searchStats.rootMovesEvaluated));
  assert.ok(move.searchStats.nodesVisited <= 100);
});
