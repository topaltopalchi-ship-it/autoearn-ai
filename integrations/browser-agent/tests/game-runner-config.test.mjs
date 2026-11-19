import test from "node:test";
import assert from "node:assert/strict";
import { resolveDetectedGame } from "../game-runner-config.mjs";

test("dispatches a detected 2048 board to its keyboard adapter", () => {
  assert.deepEqual(resolveDetectedGame({ gameType: "2048" }), {
    ok: true, gameType: "2048", adapter: "2048", allowedActions: ["press"]
  });
});

test("requires an explicit X/O choice before tic-tac-toe play", () => {
  assert.equal(resolveDetectedGame({ gameType: "tic-tac-toe" }).ok, false);
  assert.deepEqual(resolveDetectedGame({ gameType: "tic-tac-toe" }, "o"), {
    ok: true, gameType: "tic-tac-toe", adapter: "tic-tac-toe",
    player: "O", allowedActions: ["select-cell", "wait-for-turn"]
  });
});

test("refuses missing, unknown, and ambiguous detections", () => {
  assert.equal(resolveDetectedGame(null).ok, false);
  assert.equal(resolveDetectedGame({ gameType: null, reason: "ambiguous_game_candidates" }).reason,
    "ambiguous_game_candidates");
  assert.equal(resolveDetectedGame({ gameType: "snake" }).ok, false);
});
