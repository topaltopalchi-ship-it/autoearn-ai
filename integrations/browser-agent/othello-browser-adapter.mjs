import { applyOthelloMove, getOthelloLegalMoves, getOthelloOutcome } from "./games/othello-strategy.mjs";

const MARKS=new Set(["B","W"]);
export function createOthelloBrowserAdapter(page,{player,boardSelector="[data-game-board]",cellSelector="[data-game-cell][data-game-cell-index]",passSelector="[data-game-pass]"}={}) {
  if(!page||typeof page.locator!=="function") throw new TypeError("A Playwright Page is required.");
  if(!MARKS.has(player)) throw new TypeError("Othello player must be B or W.");
  async function readState() {
    const boardLocator=page.locator(boardSelector);
    if(await boardLocator.count()!==1) throw new Error("Othello requires exactly one explicitly marked board.");
    const currentRaw=String(await boardLocator.getAttribute("data-current-player")||"").toUpperCase();
    const currentPlayer=currentRaw==="BLACK"?"B":currentRaw==="WHITE"?"W":currentRaw;
    if(!MARKS.has(currentPlayer)) throw new Error("Othello board must expose data-current-player as B/W or BLACK/WHITE.");
    const cells=await boardLocator.locator(cellSelector).evaluateAll(elements=>elements.map(element=>({
      index:element.getAttribute("data-game-cell-index"),
      mark:element.getAttribute("data-mark")??element.textContent
    })));
    if(cells.length!==64) throw new Error("Othello board must expose exactly 64 indexed cells.");
    const board=Array(64).fill(null);
    for(const cell of cells) {
      if(cell.index===null||!/^\d+$/.test(cell.index)) throw new Error("Every Othello cell needs an explicit numeric index.");
      const index=Number(cell.index);
      if(!Number.isInteger(index)||index<0||index>63||board[index]!==null) throw new Error("Othello cell indices must be unique integers from 0 to 63.");
      const raw=String(cell.mark||"").trim().toUpperCase();
      if(["","-","EMPTY"].includes(raw)) board[index]="";
      else if(raw==="B"||raw==="BLACK"||raw==="X") board[index]="B";
      else if(raw==="W"||raw==="WHITE"||raw==="O") board[index]="W";
      else throw new Error("Unrecognized Othello cell mark; refusing to guess.");
    }
    const outcome=getOthelloOutcome(board);
    return {type:"othello",board,player:currentPlayer,currentPlayer,agentPlayer:player,outcome};
  }
  return {
    async observe(){return {url:page.url(),gameState:await readState()};},
    async execute(action) {
      if(action?.type==="wait-for-turn") {
        const deadline=Date.now()+30_000;
        while(Date.now()<deadline) {
          const state=await readState();
          if(state.outcome!=="playing"||state.currentPlayer===player) return {ready:true};
          await new Promise(resolve=>setTimeout(resolve,250));
        }
        return {ready:false,timedOut:true};
      }
      const state=await readState();
      if(state.outcome!=="playing"||state.currentPlayer!==player) throw new Error("It is not the agent's turn.");
      if(action?.type==="pass-turn") {
        if(getOthelloLegalMoves(state.board,player).length) throw new Error("A pass is legal only when no placement exists.");
        const pass=page.locator(boardSelector).locator(passSelector);
        if(await pass.count()!==1) throw new Error("A unique explicit data-game-pass control is required to pass.");
        const safe=await pass.evaluate(element=>{
          const rect=element.getBoundingClientRect(),style=typeof getComputedStyle==="function"?getComputedStyle(element):(element.style||{display:"block",visibility:"visible"});
          return !element.hasAttribute("disabled")&&element.getAttribute("aria-disabled")!=="true"&&style.display!=="none"&&style.visibility!=="hidden"&&rect.width>0&&rect.height>0;
        });
        if(!safe) throw new Error("Refusing to activate a hidden or disabled pass control.");
        await pass.click(); return {passed:true};
      }
      if(action?.type!=="click-cell"||!Number.isInteger(action.index)||action.index<0||action.index>63) throw new Error("Only a bounded indexed Othello cell click is allowed.");
      const expected=applyOthelloMove(state.board,action.index,player);
      const cell=page.locator(boardSelector).locator(`${cellSelector}[data-game-cell-index="${action.index}"]`);
      if(await cell.count()!==1) throw new Error("Othello move target must be one unique explicitly marked cell.");
      const safe=await cell.evaluate(element=>{
        const rect=element.getBoundingClientRect(),style=typeof getComputedStyle==="function"?getComputedStyle(element):(element.style||{display:"block",visibility:"visible"});
        return !element.closest("a,form,[role=link]")&&!element.hasAttribute("disabled")&&element.getAttribute("aria-disabled")!=="true"&&style.display!=="none"&&style.visibility!=="hidden"&&rect.width>0&&rect.height>0;
      });
      if(!safe) throw new Error("Refusing to activate a hidden, disabled, or unsafe Othello cell.");
      await cell.click(); return {index:action.index,expected};
    },
    async verify({before,after,action,result}) {
      if(action?.type==="wait-for-turn") return result?.ready===true&&(after?.gameState?.outcome!=="playing"||after?.gameState?.currentPlayer===player);
      if(action?.type==="pass-turn") return result?.passed===true&&(after?.gameState?.outcome!=="playing"||after?.gameState?.currentPlayer!==player);
      return action?.type==="click-cell"&&Array.isArray(result?.expected)&&Array.isArray(after?.gameState?.board)&&
        result.expected.every((mark,index)=>after.gameState.board[index]===mark);
    },
    isTerminal(observation){return observation?.gameState?.outcome!=="playing";}
  };
}
