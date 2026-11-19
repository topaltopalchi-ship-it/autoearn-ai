const SIZE = 8;
const EMPTY = "";
const DIRECTIONS = [[-1,-1],[-1,0],[-1,1],[0,-1],[0,1],[1,-1],[1,0],[1,1]];
const CORNERS = [0,7,56,63];

function normalizeBoard(input) {
  if (!Array.isArray(input)) throw new TypeError("Othello board must be an array.");
  const flat = input.length === 64 ? input : input.length === SIZE && input.every(row => Array.isArray(row) && row.length === SIZE) ? input.flat() : null;
  if (!flat || flat.length !== 64) throw new TypeError("Othello board must contain 64 cells.");
  return flat.map(value => {
    const mark = String(value ?? "").trim().toUpperCase();
    if (["", "-", "EMPTY"].includes(mark)) return EMPTY;
    if (mark === "B" || mark === "BLACK" || mark === "X") return "B";
    if (mark === "W" || mark === "WHITE" || mark === "O") return "W";
    throw new TypeError("Othello cells must be black, white, or empty.");
  });
}

function opponent(player) { return player === "B" ? "W" : "B"; }

export function getOthelloLegalMoves(input, player = "B") {
  const board = normalizeBoard(input);
  const own = String(player).toUpperCase();
  if (!["B","W"].includes(own)) throw new TypeError("Othello player must be B or W.");
  const other = opponent(own), moves = [];
  for (let index = 0; index < 64; index++) {
    if (board[index]) continue;
    const row = Math.floor(index / SIZE), col = index % SIZE;
    let legal = false;
    for (const [dr,dc] of DIRECTIONS) {
      let r=row+dr,c=col+dc, seenOpponent=false;
      while (r>=0 && r<SIZE && c>=0 && c<SIZE && board[r*SIZE+c]===other) {
        seenOpponent=true; r+=dr; c+=dc;
      }
      if (seenOpponent && r>=0 && r<SIZE && c>=0 && c<SIZE && board[r*SIZE+c]===own) {
        legal=true; break;
      }
    }
    if (legal) moves.push(index);
  }
  return moves;
}

export function applyOthelloMove(input, index, player = "B") {
  const board = normalizeBoard(input), own=String(player).toUpperCase();
  if (!["B","W"].includes(own)) throw new TypeError("Othello player must be B or W.");
  if (!Number.isInteger(index) || index<0 || index>=64 || !getOthelloLegalMoves(board,own).includes(index)) {
    throw new RangeError("Othello move is not legal.");
  }
  const other=opponent(own), next=[...board], row=Math.floor(index/8), col=index%8;
  next[index]=own;
  for (const [dr,dc] of DIRECTIONS) {
    let r=row+dr,c=col+dc,path=[];
    while (r>=0 && r<8 && c>=0 && c<8 && next[r*8+c]===other) {
      path.push(r*8+c); r+=dr; c+=dc;
    }
    if (path.length && r>=0 && r<8 && c>=0 && c<8 && next[r*8+c]===own) {
      for (const cell of path) next[cell]=own;
    }
  }
  return next;
}

export function getOthelloOutcome(input) {
  const board=normalizeBoard(input);
  if (getOthelloLegalMoves(board,"B").length || getOthelloLegalMoves(board,"W").length) return "playing";
  const black=board.filter(x=>x==="B").length, white=board.filter(x=>x==="W").length;
  return black===white ? "draw" : black>white ? "B" : "W";
}

const POSITION_WEIGHTS = [
  120,-25,20,10,10,20,-25,120,
  -25,-45,-5,-5,-5,-5,-45,-25,
  20,-5,15,3,3,15,-5,20,
  10,-5,3,3,3,3,-5,10,
  10,-5,3,3,3,3,-5,10,
  20,-5,15,3,3,15,-5,20,
  -25,-45,-5,-5,-5,-5,-45,-25,
  120,-25,20,10,10,20,-25,120
];

function evaluate(board, player) {
  const other=opponent(player);
  const discs=board.filter(x=>x===player).length-board.filter(x=>x===other).length;
  const mobility=getOthelloLegalMoves(board,player).length-getOthelloLegalMoves(board,other).length;
  const positional=board.reduce((sum,mark,index)=>sum+(mark===player?POSITION_WEIGHTS[index]:mark===other?-POSITION_WEIGHTS[index]:0),0);
  return positional + mobility*8 + discs;
}

function orderMoves(board, moves) {
  return [...moves].sort((a,b)=>{
    const cornerA=CORNERS.includes(a)?1:0, cornerB=CORNERS.includes(b)?1:0;
    const scoreA=cornerA*1000+POSITION_WEIGHTS[a];
    const scoreB=cornerB*1000+POSITION_WEIGHTS[b];
    return scoreB-scoreA;
  });
}

function minimax(board, player, depth, alpha, beta) {
  const ownMoves=getOthelloLegalMoves(board,player), other=opponent(player);
  const otherMoves=getOthelloLegalMoves(board,other);
  if (!ownMoves.length && !otherMoves.length) {
    const own=board.filter(x=>x===player).length, opp=board.filter(x=>x===other).length;
    return own===opp?0:own>opp?10000+own:-10000-opp;
  }
  if (depth===0) return evaluate(board,player);
  if (!ownMoves.length) return -minimax(board,other,depth-1,-beta,-alpha);
  let best=-Infinity;
  for (const move of orderMoves(board, ownMoves)) {
    const score=-minimax(applyOthelloMove(board,move,player),other,depth-1,-beta,-alpha);
    best=Math.max(best,score); alpha=Math.max(alpha,score);
    if(alpha>=beta) break;
  }
  return best;
}

export function chooseOthelloMove(input,{player="B",depth=3}={}) {
  const board=normalizeBoard(input), own=String(player).toUpperCase();
  if(!["B","W"].includes(own)) throw new TypeError("Othello player must be B or W.");
  if(!Number.isInteger(depth)||depth<1||depth>5) throw new RangeError("Othello search depth must be 1..5.");
  const moves=getOthelloLegalMoves(board,own);
  if(!moves.length) return null;
  let bestMove=null,bestScore=-Infinity;
  for(const move of orderMoves(board, moves)) {
    const score=-minimax(applyOthelloMove(board,move,own),opponent(own),depth-1,-Infinity,Infinity);
    if(score>bestScore) { bestScore=score; bestMove=move; }
  }
  return {type:"click-cell",index:bestMove};
}
