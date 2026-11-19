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
