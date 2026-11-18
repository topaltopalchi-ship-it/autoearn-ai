import { assertEquals } from "jsr:@std/assert";
import { evaluateCandidate } from "./filters.ts";

function assertRejected(url: string, title: string, description: string, reason: string) {
  const result = evaluateCandidate(url, title, description);
  if (result.accepted) throw new Error(`Expected rejection: ${reason}`);
  assertEquals(result.reason, reason);
}

Deno.test("rejects survey even when it mentions PayPal", () => assertRejected("https://example.com/survey", "Paid survey", "Earn PayPal rewards", "excluded_category"));
Deno.test("rejects referral signup bonus", () => assertRejected("https://example.com", "Invite friends", "PayPal signup bonus", "excluded_category"));
Deno.test("rejects non-HTTPS URLs", () => assertRejected("http://example.com", "Prize game", "PayPal rewards", "invalid_url"));
Deno.test("rejects games without an accepted wallet mention", () => assertRejected("https://example.com/game", "Puzzle prize game", "Free entry", "no_accepted_wallet"));
Deno.test("rejects a PayPal payment page surfaced by game search", () => assertRejected("https://paypal.com/business", "PayPal Payment Options for Global Businesses", "Merchant deals and cashback rewards", "excluded_category"));
Deno.test("rejects generic loyalty points", () => assertRejected("https://example.com/rewards", "Redeeming PayPal Rewards points", "Donate points to a cause", "excluded_category"));
Deno.test("rejects editorial play-to-earn directories", () => assertRejected("https://example.com/archive", "Play to earn games archives", "Latest news and best games to watch", "excluded_category"));
Deno.test("rejects token price pages even when game token named", () => assertRejected("https://coindesk.com/price/play", "PLAY price chart", "Gaming token price, market cap and crypto", "excluded_category"));
Deno.test("rejects game pages that mention wallet but no actual prize", () => assertRejected("https://example.com/game", "Free online puzzle game", "Play now with PayPal available", "missing_reward_evidence"));
Deno.test("rejects prize games without explicit payout context", () => assertRejected("https://example.com/game", "Puzzle contest cash prize", "Win cash and prizes. PayPal mentioned.", "missing_payout_evidence"));
Deno.test("accepts a free puzzle contest with explicit Skrill payout", () => {
  assertEquals(evaluateCandidate("https://example.com/contest", "Puzzle contest cash prize", "Free entry. Winners receive payout via Skrill; minimum withdrawal applies."), {
    accepted: true, url: "https://example.com/contest", wallets: ["Skrill"],
  });
});
Deno.test("accepts crypto game with explicit USDT prize payout", () => {
  assertEquals(evaluateCandidate("https://example.com/play", "Online game cash prize", "Winners receive prize payout in USDT. Free entry."), {
    accepted: true, url: "https://example.com/play", wallets: ["Crypto"],
  });
});
