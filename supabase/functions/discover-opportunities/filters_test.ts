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

Deno.test("rejects a PayPal payment page incorrectly surfaced by a game search", () => {
  assertRejected("https://paypal.com/business", "PayPal Payment Options for Global Businesses", "Merchant deals and cashback rewards", "excluded_category");
});

Deno.test("rejects generic loyalty points even when PayPal is mentioned", () => {
  assertRejected("https://example.com/rewards", "Redeeming PayPal Rewards points", "Donate points to a cause", "excluded_category");
});

Deno.test("rejects editorial play-to-earn directories", () => {
  assertRejected("https://example.com/archive", "Play to earn games archives", "Latest news and best games to watch", "excluded_category");
});

Deno.test("rejects wallet pages with no actual game or contest signal", () => {
  assertRejected("https://example.com/paypal", "Free PayPal cash card options", "Earn rewards and cash", "excluded_category");
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
