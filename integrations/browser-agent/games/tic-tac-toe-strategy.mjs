const WIN_LINES = [
  [0, 1, 2], [3, 4, 5], [6, 7, 8],
  [0, 3, 6], [1, 4, 7], [2, 5, 8],
  [0, 4, 8], [2, 4, 6]
];

function normalizeBoard(board) {
  if (!Array.isArray(board) || board.length !== 9) {
    throw new TypeError("Tic-tac-toe board must contain exactly 9 cells.");
  }
  const normalized = board.map(cell => {
    if (cell === null || cell === "" || cell === " " || cell === "-") return null;
    if (typeof cell === "string" && ["X", "O"].includes(cell.toUpperCase())) return cell.toUpperCase();
    throw new TypeError("Tic-tac-toe cells must be X, O, or empty.");
  });
  const xCount = normalized.filter(cell => cell === "X").length;
  const oCount = normalized.filter(cell => cell === "O").length;
  if (oCount > xCount || xCount > oCount + 1) {
    throw new TypeError("Tic-tac-toe board has impossible mark counts.");
  }
  const xWon = WIN_LINES.some(line => line.every(index => normalized[index] === "X"));
  const oWon = WIN_LINES.some(line => line.every(index => normalized[index] === "O"));
  if (xWon && oWon) throw new TypeError("Tic-tac-toe board cannot have two winners.");
  if ((xWon && xCount !== oCount + 1) || (oWon && xCount !== oCount)) {
    throw new TypeError("Tic-tac-toe winner conflicts with move counts.");
  }
  return normalized;
}

function winner(board) {
  for (const [a, b, c] of WIN_LINES) {
    if (board[a] && board[a] === board[b] && board[a] === board[c]) return board[a];
  }
  return null;
}

function minimax(board, player, memo) {
  const key = board.map(cell => cell || ".").join("") + ":" + player;
  if (memo.has(key)) return memo.get(key);
  const won = winner(board);
  const depth = board.filter(Boolean).length;
  if (won) return won === "X" ? 10 - depth : depth - 10;
  if (depth === 9) return 0;

  let best = player === "X" ? -Infinity : Infinity;
  for (let index = 0; index < 9; index++) {
    if (board[index] !== null) continue;
    board[index] = player;
    const score = minimax(board, player === "X" ? "O" : "X", memo);
    board[index] = null;
    best = player === "X" ? Math.max(best, score) : Math.min(best, score);
  }
  memo.set(key, best);
  return best;
}

/** Returns an optimal cell index; X moves first and both sides are assumed optimal. */
export function chooseTicTacToeMove(inputBoard, { player } = {}) {
  const board = normalizeBoard(inputBoard);
  const xCount = board.filter(cell => cell === "X").length;
  const oCount = board.filter(cell => cell === "O").length;
  const nextPlayer = player || (xCount === oCount ? "X" : "O");
  if (!["X", "O"].includes(nextPlayer)) throw new TypeError("Player must be X or O.");
  if (nextPlayer !== (xCount === oCount ? "X" : "O")) {
    throw new TypeError("Player does not match the board turn.");
  }
  if (winner(board) || board.every(Boolean)) return null;

  const memo = new Map();
  let bestIndex = null;
  let bestScore = nextPlayer === "X" ? -Infinity : Infinity;
  for (let index = 0; index < 9; index++) {
    if (board[index] !== null) continue;
    board[index] = nextPlayer;
    const score = minimax(board, nextPlayer === "X" ? "O" : "X", memo);
    board[index] = null;
    if (nextPlayer === "X" ? score > bestScore : score < bestScore) {
      bestScore = score;
      bestIndex = index;
    }
  }
  return { index: bestIndex, mark: nextPlayer, score: bestScore };
}

export function getTicTacToeOutcome(inputBoard) {
  const board = normalizeBoard(inputBoard);
  const won = winner(board);
  if (won) return won === "X" ? "x_won" : "o_won";
  return board.every(Boolean) ? "draw" : "playing";
}
