import test from "node:test";
import assert from "node:assert/strict";
import { decideKnownGame } from "../games/game-strategy-registry.mjs";
import { getOthelloLegalMoves } from "../games/othello-strategy.mjs";

function openingBoard() {
  const board=Array(64).fill("");
  board[27]="W"; board[28]="B"; board[35]="B"; board[36]="W";
  return board;
}

test("registry dispatches Othello state to a legal indexed placement",async()=>{
  const board=openingBoard();
  const action=await decideKnownGame({gameState:{
    type:"othello",board,player:"B",currentPlayer:"B",agentPlayer:"B",outcome:"playing"
  }});
  assert.equal(action.type,"click-cell");
  assert.ok(getOthelloLegalMoves(board,"B").includes(action.index));
});

test("registry waits rather than moving on the opponent's Othello turn",async()=>{
  const action=await decideKnownGame({gameState:{
    type:"othello",board:openingBoard(),player:"W",currentPlayer:"W",agentPlayer:"B",outcome:"playing"
  }});
  assert.deepEqual(action,{type:"wait-for-turn"});
});
