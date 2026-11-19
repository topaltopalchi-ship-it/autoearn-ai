import test from "node:test";
import assert from "node:assert/strict";
import { chooseTicTacToeMove, getTicTacToeOutcome } from "../games/tic-tac-toe-strategy.mjs";
import { decideKnownGame, getGameStrategy, registerGameStrategy } from "../games/game-strategy-registry.mjs";

test("takes an immediate winning move", () => {
  const result = chooseTicTacToeMove(["X", "X", null, "O", "O", null, null, null, null]);
  assert.equal(result.index, 2);
  assert.equal(result.mark, "X");
});

test("blocks an opponent's immediate win", () => {
  const result = chooseTicTacToeMove(["O", "O", null, "X", null, null, "X", null, null]);
  assert.equal(result.index, 2);
});

test("never loses against an optimal opponent from an empty board", () => {
  const first = chooseTicTacToeMove(Array(9).fill(null));
  assert.ok([0, 2, 4, 6, 8].includes(first.index));
});

test("returns no move for a finished game", () => {
  assert.equal(chooseTicTacToeMove(["X", "X", "X", "O", "O", null, null, null, null]), null);
  assert.equal(getTicTacToeOutcome(["X", "O", "X", "X", "O", "O", "O", "X", "X"]), "draw");
});

test("rejects impossible boards and mismatched turns", () => {
  assert.throws(() => chooseTicTacToeMove(["O", null, null, null, null, null, null, null, null]), /impossible/);
  assert.throws(() => chooseTicTacToeMove(Array(9).fill(null), { player: "O" }), /does not match/);
});

test("registry safely declines unsupported game types", async () => {
  assert.equal(await decideKnownGame({ gameState: { type: "unknown" } }), null);
  assert.equal(getGameStrategy("unknown"), null);
});

test("registry exposes a deterministic tic-tac-toe move", async () => {
  const move = await decideKnownGame({
    gameState: { type: "tic-tac-toe", board: Array(9).fill(null), player: "X" }
  });
  assert.ok(move);
  assert.equal(move.type, "select-cell");
  assert.ok(move.index >= 0 && move.index < 9);
});

test("custom strategy registration validates inputs", () => {
  assert.throws(() => registerGameStrategy("Bad Name", () => null), /identifier/);
  assert.throws(() => registerGameStrategy("custom", null), /function/);
});
