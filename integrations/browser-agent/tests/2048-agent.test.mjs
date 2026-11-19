import test from "node:test";
import assert from "node:assert/strict";
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
