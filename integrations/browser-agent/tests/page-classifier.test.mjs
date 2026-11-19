import test from "node:test";
import assert from "node:assert/strict";
import { classifySitePage } from "../page-classifier.mjs";

test("classifies folder pages from category labels", () => {
  const result = classifySitePage({
    title: "Arcade Categories",
    snapshot: "heading Arcade Categories",
    navigationTargets: [{ name: "Puzzle room" }, { name: "Action games" }]
  });
  assert.equal(result.type, "folder");
  assert.equal(result.safeToExplore, true);
});

test("classifies a game page from canvas, score and game controls", () => {
  const result = classifySitePage({
    title: "Puzzle Game",
    snapshot: "canvas game board Score: 120",
    navigationTargets: [{ name: "Restart game" }, { name: "Move left" }]
  });
  assert.equal(result.type, "game");
  assert.equal(result.safeToExplore, true);
});

test("blocks verification and login pages from exploration", () => {
  const verification = classifySitePage({ title: "Security challenge", snapshot: "Verify you are human" });
  const login = classifySitePage({ title: "Sign in", snapshot: "Password" });
  assert.equal(verification.type, "verification");
  assert.equal(verification.safeToExplore, false);
  assert.equal(login.type, "login");
  assert.equal(login.safeToExplore, false);
});

test("keeps ambiguous pages unknown", () => {
  const result = classifySitePage({ title: "Welcome", snapshot: "Welcome to our website" });
  assert.equal(result.type, "unknown");
  assert.equal(result.confidence, 0);
});
