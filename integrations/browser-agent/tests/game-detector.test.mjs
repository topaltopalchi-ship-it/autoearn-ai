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
});

test("recognizes Connect Four only from exactly 42 uniquely indexed X/O/empty cells", () => {\n  const cells = Array.from({ length: 42 }, (_, index) => ({ index, mark: index === 41 ? "X" : "" }));\n  const result = detectKnownGame({ gameCandidates: [{ kind: "connect-four", boardKey: "board-c", cells }] });\n  assert.equal(result.gameType, "connect-four");\n  assert.equal(isSupportedGameType("connect-four"), true);\n  assert.equal(detectKnownGame({ gameCandidates: [{ kind: "connect-four", cells: cells.slice(1) }] }).gameType, null);\n});\n\ntest("recognizes 2048 only from valid coordinate and power-of-two tile metadata", () => {
  const tiles = [{ x: 0, y: 0, value: 2 }, { x: 2, y: 1, value: 4 }, { x: 3, y: 3, value: 8 }];
  const result = detectKnownGame({ gameCandidates: [{ kind: "2048", boardKey: "board-b", tiles }] });
  assert.equal(result.gameType, "2048");
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
