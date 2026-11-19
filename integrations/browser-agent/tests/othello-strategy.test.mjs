import test from "node:test";
import assert from "node:assert/strict";
import { applyOthelloMove, chooseOthelloMove, getOthelloLegalMoves, getOthelloOutcome } from "../games/othello-strategy.mjs";

function initialBoard() {
  const board=Array(64).fill("");
  board[27]="W"; board[28]="B"; board[35]="B"; board[36]="W";
  return board;
}

test("finds the four legal opening moves and returns a legal move",()=>{
  const board=initialBoard();
  assert.deepEqual(getOthelloLegalMoves(board,"B"),[20,29,34,43]);
  const move=chooseOthelloMove(board,{player:"B",depth:3});
  assert.ok(getOthelloLegalMoves(board,"B").includes(move.index));
});

test("applies a legal move and flips the bracketed opponent disc",()=>{
  const board=initialBoard();
  const next=applyOthelloMove(board,20,"B");
  assert.equal(next[20],"B");
  assert.equal(next[28],"B");
  assert.equal(board[28],"B");
});

test("detects a terminal winner and refuses illegal moves",()=>{
  const board=Array(64).fill("B");
  assert.equal(getOthelloOutcome(board),"B");
  assert.throws(()=>applyOthelloMove(initialBoard(),0,"B"),/not legal/);
});

test("returns no move when the player has no legal placement",()=>{
  const board=Array(64).fill("B");
  board[0]="";
  assert.equal(chooseOthelloMove(board,{player:"W"}),null);
});
