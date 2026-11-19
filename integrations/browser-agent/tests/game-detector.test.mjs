import test from "node:test";
import assert from "node:assert/strict";
import { detectKnownGame, isSupportedGameType } from "../game-detector.mjs";

test("recognizes a uniquely indexed nine-cell tic-tac-toe board", () => {
  const cells = Array.from({ length: 9 }, (_, index) => ({
    index, mark: index === 0 ? "X" : index === 4 ? "O" : ""
  }));
  const result = detectKnownGame({ gameCandidates: [{ kind: "tic-tac-toe", boardKey: "board-a", cells }] });
  assert.equal(result.gameType, "tic-tac-toe");
  assert.equal(result.confidence, 0.99);

  const wrongTurn = cells.map(cell => ({ ...cell, mark: cell.index === 0 ? "O" : "" }));
  assert.equal(detectKnownGame({ gameCandidates: [{ kind: "tic-tac-toe", cells: wrongTurn }] }).gameType, null);
  const dualWinner = cells.map(cell => ({ ...cell, mark:
    cell.index <= 2 ? "X" : cell.index >= 3 && cell.index <= 5 ? "O" : "" }));
  assert.equal(detectKnownGame({ gameCandidates: [{ kind: "tic-tac-toe", cells: dualWinner }] }).gameType, null);
  const winnerOutOfTurn = cells.map(cell => ({ ...cell, mark:
    cell.index <= 2 ? "O" : cell.index === 3 || cell.index === 4 || cell.index === 6 || cell.index === 7 ? "X" : "" }));
  assert.equal(detectKnownGame({ gameCandidates: [{ kind: "tic-tac-toe", cells: winnerOutOfTurn }] }).gameType, null);
});

test("recognizes Connect Four only from exactly 42 uniquely indexed X/O/empty cells", () => {
  const cells = Array.from({ length: 42 }, (_, index) => ({ index, mark: index === 41 ? "X" : "" }));
  const result = detectKnownGame({ gameCandidates: [{ kind: "connect-four", boardKey: "board-c", cells }] });
  assert.equal(result.gameType, "connect-four");
  assert.equal(isSupportedGameType("connect-four"), true);
  assert.equal(detectKnownGame({ gameCandidates: [{ kind: "connect-four", cells: cells.slice(1) }] }).gameType, null);

  const floating = cells.map(cell => ({ ...cell, mark: cell.index === 23 ? "X" : "" }));
  assert.equal(detectKnownGame({ gameCandidates: [{ kind: "connect-four", cells: floating }] }).gameType, null);

  const dualWin = cells.map(cell => {
    const row = Math.floor(cell.index / 7), col = cell.index % 7;
    return { ...cell, mark: row === 5 && col < 4 ? "X" : row === 4 && col < 4 ? "O" : "" };
  });
  assert.equal(detectKnownGame({ gameCandidates: [{ kind: "connect-four", cells: dualWin }] }).gameType, null);

  const wrongTurn = cells.map(cell => ({ ...cell, mark: cell.index === 35 ? "O" : "" }));
  assert.equal(detectKnownGame({ gameCandidates: [{ kind: "connect-four", cells: wrongTurn }] }).gameType, null);
  const winnerOutOfTurn = cells.map(cell => {
    const row = Math.floor(cell.index / 7), col = cell.index % 7;
    const mark = row === 5 && col < 4 ? "O" :
      row === 5 && col >= 4 ? "X" :
      row === 4 && (col === 4 || col === 5) ? "X" : "";
    return { ...cell, mark };
  });
  assert.equal(detectKnownGame({ gameCandidates: [{ kind: "connect-four", cells: winnerOutOfTurn }] }).gameType, null);
});

test("recognizes Othello only from 64 indexed cells and an explicit current player", () => {
  const cells = Array.from({ length: 64 }, (_, index) => ({ index, mark: index === 27 || index === 36 ? "W" : index === 28 || index === 35 ? "B" : "" }));
  assert.equal(detectKnownGame({ gameCandidates: [{ kind: "othello", cells, currentPlayer: "B" }] }).gameType, "othello");
  assert.equal(detectKnownGame({ gameCandidates: [{ kind: "othello", cells, currentPlayer: "" }] }).gameType, null);
  assert.equal(detectKnownGame({ gameCandidates: [{ kind: "othello", cells: cells.slice(1), currentPlayer: "B" }] }).gameType, null);
  const duplicate = cells.map(cell => ({ ...cell, index: cell.index === 63 ? 62 : cell.index }));
  assert.equal(detectKnownGame({ gameCandidates: [{ kind: "othello", cells: duplicate, currentPlayer: "B" }] }).gameType, null);
  const unknownMark = cells.map(cell => ({ ...cell, mark: cell.index === 0 ? "RED" : cell.mark }));
  assert.equal(detectKnownGame({ gameCandidates: [{ kind: "othello", cells: unknownMark, currentPlayer: "B" }] }).gameType, null);
});

test("recognizes 2048 only from valid coordinate and power-of-two tile metadata", () => {
  const tiles = [{ x: 0, y: 0, value: 2 }, { x: 2, y: 1, value: 4 }, { x: 3, y: 3, value: 8 }];
  const result = detectKnownGame({ gameCandidates: [{ kind: "2048", boardKey: "board-b", tiles }] });
  assert.equal(result.gameType, "2048");
  const unsafeLarge = [{ x: 0, y: 0, value: 4294967297 }, { x: 1, y: 1, value: 4 }];
  assert.equal(detectKnownGame({ gameCandidates: [{ kind: "2048", tiles: unsafeLarge }] }).gameType, null);
  const validLargePower = [{ x: 0, y: 0, value: 4294967296 }, { x: 1, y: 1, value: 4 }];
  assert.equal(detectKnownGame({ gameCandidates: [{ kind: "2048", tiles: validLargePower }] }).gameType, "2048");
});

test("refuses malformed and ambiguous game candidates", () => {
  const malformed = detectKnownGame({ gameCandidates: [{
    kind: "tic-tac-toe", cells: Array.from({ length: 9 }, (_, index) => ({ index: index === 8 ? 7 : index, mark: "" }))
  }] });
  assert.equal(malformed.gameType, null);
  const ambiguous = detectKnownGame({ gameCandidates: [
    { kind: "tic-tac-toe", cells: Array.from({ length: 9 }, (_, index) => ({ index, mark: "" })) },
    { kind: "2048", tiles: [{ x: 0, y: 0, value: 2 }, { x: 1, y: 1, value: 4 }] }
  ] });
  assert.equal(ambiguous.gameType, null);
  assert.equal(ambiguous.reason, "ambiguous_game_candidates");
});

test("does not guess from text or unsupported game signatures", () => {
  assert.equal(detectKnownGame({ title: "2048 game score 100" }).gameType, null);
  assert.equal(isSupportedGameType("2048"), true);
  assert.equal(isSupportedGameType("snake"), false);
});
