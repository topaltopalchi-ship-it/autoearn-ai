import { assertEquals } from "jsr:@std/assert";
import { evaluateCandidate } from "./filters.ts";

Deno.test("rejects survey even when it mentions PayPal", () => {
  assertEquals(evaluateCandidate("https://example.com/survey", "Paid survey", "Earn PayPal rewards").reason, "excluded_category");
});

Deno.test("rejects referral signup bonus", () => {
  assertEquals(evaluateCandidate("https://example.com", "Invite friends", "PayPal signup bonus").reason, "excluded_category");
});

Deno.test("rejects non-HTTPS URLs", () => {
  assertEquals(evaluateCandidate("http://example.com", "Prize game", "PayPal rewards").reason, "invalid_url");
});

Deno.test("rejects games without an accepted wallet mention", () => {
  assertEquals(evaluateCandidate("https://example.com/game", "Puzzle prize game", "Free entry").reason, "no_accepted_wallet");
});

Deno.test("accepts a free puzzle contest mentioning Skrill", () => {
  assertEquals(evaluateCandidate("https://example.com/contest", "Puzzle contest", "Free entry; Skrill payout"), {
    accepted: true,
    url: "https://example.com/contest",
    wallets: ["Skrill"],
  });
});

Deno.test("accepts crypto game with USDT mention", () => {
  assertEquals(evaluateCandidate("https://example.com/play", "Online game", "USDT rewards"), {
    accepted: true,
    url: "https://example.com/play",
    wallets: ["Crypto"],
  });
});
