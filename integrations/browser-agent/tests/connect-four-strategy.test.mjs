import test from "node:test";
import assert from "node:assert/strict";
import { chooseConnectFourMove, getConnectFourOutcome } from "../games/connect-four-strategy.mjs";

const empty = () => Array.from({ length: 6 }, () => Array(7).fill(""));

test("Connect Four takes an immediate winning move", () => {
  const board = empty();
  for (let c = 0; c < 3; c++) board[5][c] = "X";
  for (let c = 4; c < 7; c++) board[5][c] = "O";
  assert.deepEqual(chooseConnectFourMove(board, { player: "X" }), {
    type: "drop-column", column: 3, index: 38
  });
});

test("Connect Four blocks an opponent's immediate horizontal win", () => {
  const board = empty();
  for (let c = 0; c < 3; c++) board[5][c] = "O";
  board[5][4] = board[5][5] = board[5][6] = "X";
  board[4][4] = "X";
  const move = chooseConnectFourMove(board, { player: "X" });
  assert.equal(move.column, 3);
});

test("Connect Four prefers the center on an empty board", () => {
  assert.equal(chooseConnectFourMove(empty(), { player: "X" }).column, 3);
});

test("Connect Four refuses to move out of turn", () => {
  const board = empty();
  assert.throws(() => chooseConnectFourMove(board, { player: "O" }), /It is X's turn/);
  board[5][0] = "X";
  assert.throws(() => chooseConnectFourMove(board, { player: "X" }), /It is O's turn/);
  assert.equal(chooseConnectFourMove(board, { player: "O" }).column >= 0, true);
});

test("Connect Four detects win, draw and invalid board shapes", () => {
  const won = empty();
  for (let c = 0; c < 4; c++) won[5][c] = "X";
  for (let c = 4; c < 7; c++) won[5][c] = "O";
  assert.equal(getConnectFourOutcome(won), "X");
  const draw = [
    "XXXOOOX", "OXOOXXO", "XOXXOXX", "XOOOXOO", "XOXXXOX", "OXOOOXO"
  ].map(row => row.split(""));
  assert.equal(getConnectFourOutcome(draw), "draw");
  assert.throws(() => chooseConnectFourMove([[ "X" ]]), /42 valid/);
  const floating = empty();
  floating[3][2] = "X";
  assert.throws(() => chooseConnectFourMove(floating), /violates gravity/);
  const impossible = empty();
  for (let c = 0; c < 4; c++) { impossible[5][c] = "X"; impossible[4][c] = "O"; }
  assert.throws(() => getConnectFourOutcome(impossible), /wins for both/);
  const wrongTurn = empty();
  wrongTurn[5][0] = "O";
  assert.throws(() => getConnectFourOutcome(wrongTurn), /turn counts/);
  const wrongWinner = empty();
  for (let c = 0; c < 4; c++) wrongWinner[5][c] = "O";
  wrongWinner[5][4] = wrongWinner[5][5] = wrongWinner[5][6] = "X";
  wrongWinner[4][4] = wrongWinner[4][5] = "X";
  assert.throws(() => getConnectFourOutcome(wrongWinner), /winner is inconsistent/);
});
