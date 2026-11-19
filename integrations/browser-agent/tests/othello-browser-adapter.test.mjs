import test from "node:test";
import assert from "node:assert/strict";
import { applyOthelloMove } from "../games/othello-strategy.mjs";
import { createOthelloBrowserAdapter } from "../othello-browser-adapter.mjs";

function initialBoard() {
  const board=Array(64).fill("");
  board[27]="W"; board[28]="B"; board[35]="B"; board[36]="W";
  return board;
}
function fakePage() {
  let board=initialBoard(), current="B", clicked=null;
  const boardLocator={
    count:async()=>1,
    getAttribute:async name=>name==="data-current-player"?current:null,
    locator(selector) {
      if(selector.startsWith("[data-game-cell][data-game-cell-index]")) return {
        evaluateAll:async callback=>callback(board.map((mark,index)=>({
          getAttribute:name=>name==="data-game-cell-index"?String(index):name==="data-mark"?mark:null,
          textContent:mark
        })))
      };
      const match=selector.match(/data-game-cell-index="(\d+)"/);
      const index=match?Number(match[1]):-1;
      return {
        count:async()=>index>=0&&index<64?1:0,
        evaluate:async callback=>callback({
          closest:()=>null,hasAttribute:()=>false,getAttribute:()=>null,
          getBoundingClientRect:()=>({width:30,height:30}),
          style:{display:"block",visibility:"visible"}
        }),
        click:async()=>{clicked=index;board=applyOthelloMove(board,index,"B");current="W";}
      };
    }
  };
  return {locator:()=>boardLocator,url:()=>"https://game.example/othello",get clicked(){return clicked;}};
}

test("reads Othello board, plays a legal indexed square, and verifies all flips",async()=>{
  const page=fakePage(),adapter=createOthelloBrowserAdapter(page,{player:"B"});
  const before=await adapter.observe();
  const result=await adapter.execute({type:"click-cell",index:19});
  const after=await adapter.observe();
  assert.equal(page.clicked,19);
  assert.equal(await adapter.verify({before,after,action:{type:"click-cell",index:19},result}),true);
});

test("refuses a move when it is not the configured player's turn",async()=>{
  const page=fakePage(),adapter=createOthelloBrowserAdapter(page,{player:"W"});
  await assert.rejects(()=>adapter.execute({type:"click-cell",index:19}),/not the agent's turn/);
});
