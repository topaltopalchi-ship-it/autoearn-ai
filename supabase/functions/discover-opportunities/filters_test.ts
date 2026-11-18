import { assertEquals } from "jsr:@std/assert";
import { evaluateCandidate } from "./filters.ts";

function assertRejected(url: string, title: string, description: string, reason: string) {
  const result = evaluateCandidate(url, title, description);
  if (result.accepted) throw new Error(`Expected rejection: ${reason}`);
  assertEquals(result.reason, reason);
}

Deno.test("rejects survey even when it mentions PayPal", () => {
  assertRejected("https://example.com/survey", "Paid survey", "Earn PayPal rewards", "excluded_category");
});

Deno.test("rejects referral signup bonus", () => {
  assertRejected("https://example.com", "Invite friends", "PayPal signup bonus", "excluded_category");
});

Deno.test("rejects non-HTTPS URLs", () => {
  assertRejected("http://example.com", "Prize game", "PayPal rewards", "invalid_url");
});

Deno.test("rejects games without an accepted wallet mention", () => {
  assertRejected("https://example.com/game", "Puzzle prize game", "Free entry", "no_accepted_wallet");
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
