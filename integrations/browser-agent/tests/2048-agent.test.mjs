import test from "node:test";
import assert from "node:assert/strict";
import "../../../static/game-agent.js";
import { create2048Decision } from "../games/2048-strategy.mjs";

test("2048 decision emits a valid arrow-key action from an observed board", async () => {
  const decide = create2048Decision();
  const action = await decide({
    board: [
      [2, 2, 0, 0],
      [0, 0, 0, 0],
      [0, 0, 0, 0],
      [0, 0, 0, 0]
    ]
  });
  assert.equal(action.type, "press");
  assert.ok(["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"].includes(action.key));
});

test("2048 decision refuses to guess when no board is observable", async () => {
  const decide = create2048Decision();
  assert.equal(await decide({ snapshot: "unknown game screen" }), null);
});

test("game-agent loop executes a 2048 move and stops on a verified win", async () => {
  let board = [
    [2, 0, 0, 0],
    [0, 0, 0, 0],
    [0, 0, 0, 0],
    [0, 0, 0, 0]
  ];
  const actions = [];
  const adapter = {
    async observe() {
      return { board: board.map(row => [...row]), outcome: board[0][0] === 2048 ? "won" : "playing" };
    },
    async execute(action) {
      actions.push(action);
      board = [
        [2048, 0, 0, 0],
        [0, 0, 0, 0],
        [0, 0, 0, 0],
        [0, 0, 0, 0]
      ];
      return { accepted: true };
    },
    async verify({ before, after }) {
      return before.board[0][0] !== after.board[0][0];
    },
    isTerminal(observation) {
      return observation.outcome === "won" || observation.outcome === "game_over";
    }
  };
  const agent = globalThis.AutoEarnGameAgent.createAgent({
    adapter,
    decide: create2048Decision(),
    limits: { maxSteps: 5, maxDurationMs: 2_000, allowedActions: ["press"] }
  });
  const result = await agent.run();
  assert.equal(result.status, "completed");
  assert.equal(result.reason, "terminal_state");
  assert.equal(result.steps, 1);
  assert.equal(actions.length, 1);
  assert.equal(actions[0].type, "press");
  assert.match(actions[0].key, /^Arrow/);
});
