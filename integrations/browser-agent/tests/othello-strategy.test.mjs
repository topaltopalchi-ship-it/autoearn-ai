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
  assert.deepEqual(getOthelloLegalMoves(board,"B"),[19,26,37,44]);
  const move=chooseOthelloMove(board,{player:"B",depth:3});
  assert.ok(getOthelloLegalMoves(board,"B").includes(move.index));
});

test("applies a legal move and flips the bracketed opponent disc",()=>{
  const board=initialBoard();
  const next=applyOthelloMove(board,19,"B");
  assert.equal(next[19],"B");
  assert.equal(next[27],"B");
  assert.equal(board[27],"W");
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

test("rejects malformed boards, invalid players, and unbounded search depths",()=>{
  assert.throws(()=>getOthelloLegalMoves(Array(63).fill(""),"B"),/64 cells/);
  assert.throws(()=>getOthelloLegalMoves(initialBoard(),"R"),/player must be B or W/);
  assert.throws(()=>chooseOthelloMove(initialBoard(),{player:"B",depth:0}),/depth must be 1..5/);
  const malformed=initialBoard(); malformed[0]="RED";
  assert.throws(()=>getOthelloOutcome(malformed),/black, white, or empty/);
});

test("accepts a two-dimensional board and normalizes documented disc aliases",()=>{
  const board=Array.from({length:8},()=>Array(8).fill(""));
  board[3][3]="white"; board[3][4]="x"; board[4][3]="black"; board[4][4]="o";
  assert.deepEqual(getOthelloLegalMoves(board,"B"),[19,26,37,44]);
});

test("prioritizes an available corner over an ordinary legal move",()=>{
  const board=Array(64).fill("");
  board[1]="W"; board[2]="B";
  board[8]="W"; board[16]="B";
  board[10]="W"; board[11]="B";
  const legal=getOthelloLegalMoves(board,"B");
  assert.ok(legal.includes(0));
  assert.ok(legal.includes(9));
  assert.equal(chooseOthelloMove(board,{player:"B",depth:1}).index,0);
});
