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
Deno.test("accepts prize game without naming a specific wallet", () => { assertEquals(evaluateCandidate("https://example.com/game", "Puzzle contest cash prize", "Free entry. Winners receive payout after withdrawal request."), { accepted: true, url: "https://example.com/game", payoutMethods: [] }); });
Deno.test("rejects a PayPal payment page surfaced by game search", () => assertRejected("https://paypal.com/business", "PayPal Payment Options for Global Businesses", "Merchant deals and cashback rewards", "excluded_category"));
Deno.test("rejects generic loyalty points", () => assertRejected("https://example.com/rewards", "Redeeming PayPal Rewards points", "Donate points to a cause", "excluded_category"));
Deno.test("rejects editorial play-to-earn directories", () => assertRejected("https://example.com/archive", "Play to earn games archives", "Latest news and best games to watch", "excluded_category"));
Deno.test("rejects token price pages even when game token named", () => assertRejected("https://coindesk.com/price/play", "PLAY price chart", "Gaming token price, market cap and crypto", "excluded_category"));
Deno.test("rejects game pages that mention wallet but no actual prize", () => assertRejected("https://example.com/game", "Free online puzzle game", "Play now with PayPal available", "missing_reward_evidence"));
Deno.test("rejects prize games without explicit payout context", () => assertRejected("https://example.com/game", "Puzzle contest cash prize", "Win cash and prizes. PayPal mentioned.", "missing_payout_evidence"));
Deno.test("accepts a free puzzle contest with explicit Skrill payout", () => {
  assertEquals(evaluateCandidate("https://example.com/contest", "Puzzle contest cash prize", "Free entry. Winners receive payout via Skrill; minimum withdrawal applies."), {
    accepted: true, url: "https://example.com/contest", payoutMethods: ["Skrill"],
  });
});
Deno.test("accepts crypto game with explicit USDT prize payout", () => {
  assertEquals(evaluateCandidate("https://example.com/play", "Online game cash prize", "Winners receive prize payout in USDT. Free entry."), {
    accepted: true, url: "https://example.com/play", payoutMethods: ["Crypto"],
  });
});

Deno.test("accepts bank card payout without crypto wallet", () => {
  assertEquals(evaluateCandidate("https://example.com/game", "Online game cash prize", "Winners receive cash prize paid by bank card. Free entry."), {
    accepted: true, url: "https://example.com/game", payoutMethods: ["Bank card"],
  });
});
Deno.test("accepts bank transfer payout without crypto wallet", () => {
  assertEquals(evaluateCandidate("https://example.com/game", "Puzzle tournament prize money", "Prize payout by bank transfer to bank account. Free entry."), {
    accepted: true, url: "https://example.com/game", payoutMethods: ["Bank transfer"],
  });
});

Deno.test("accepts a free spin wheel with a cash prize and payout", () => {
  assertEquals(evaluateCandidate("https://example.com/wheel", "Daily lucky spin wheel cash prize", "One free spin every day, no purchase necessary. Winners receive payout by bank transfer."), {
    accepted: true, url: "https://example.com/wheel", payoutMethods: ["Bank transfer"],
  });
});
Deno.test("accepts a free raffle with a prize draw and card payout", () => {
  const result = evaluateCandidate("https://example.com/raffle", "Free raffle prize draw win a car", "Free entry, no purchase required. Prize paid to winners by bank card.");
  if (!result.accepted) throw new Error(`Expected free raffle to be accepted, got: ${result.reason}`);
  assertEquals(result.payoutMethods, ["Bank card"]);
  assertEquals(result.url, "https://example.com/raffle");
});
Deno.test("accepts a free sweepstakes with a gift card prize", () => {
  assertEquals(evaluateCandidate("https://example.com/sweepstakes", "Free sweepstakes win a gift card", "No purchase necessary. Prize payout is delivered by Visa gift card."), {
    accepted: true, url: "https://example.com/sweepstakes", payoutMethods: ["Bank card"],
  });
});
Deno.test("rejects a paid raffle with no free entry route", () => {
  assertRejected("https://example.com/raffle", "Paid raffle win a car", "Buy a ticket, entry fee required. Prize paid by bank transfer.", "excluded_category");
});
Deno.test("rejects a spin wheel with no real prize or payout evidence", () => {
  assertRejected("https://example.com/wheel", "Lucky spin wheel game", "Spin for fun and collect points.", "missing_reward_evidence");
});

Deno.test("accepts a free sports prediction contest with a real prize payout", () => {
  const result = evaluateCandidate("https://example.com/predictor", "Free football match prediction contest cash prize", "No purchase required. Predict match scores for free; top players receive a cash prize paid by bank transfer.");
  if (!result.accepted) throw new Error(`Expected free prediction contest to be accepted, got: ${result.reason}`);
  assertEquals(result.payoutMethods, ["Bank transfer"]);
});
Deno.test("rejects a sports prediction page that requires a wager", () => {
  assertRejected("https://example.com/predict", "Football prediction contest cash prize", "Stake required on each match. Winners receive cash payout by bank transfer.", "excluded_category");
});
Deno.test("accepts explicit no-entry-fee wording", () => {
  const result = evaluateCandidate("https://example.com/free-picks", "Free score prediction contest prize money", "No entry fee and no purchase necessary. Winners receive prize payout by bank transfer.");
  if (!result.accepted) throw new Error(`Expected no-entry-fee contest to be accepted, got: ${result.reason}`);
});

Deno.test("rejects a prize game with payout but no evidence that entry is free", () => {\n  assertRejected("https://example.com/game", "Online game cash prize", "Winners receive cash prize payout by bank transfer.", "missing_free_entry_evidence");\n});\n\nDeno.test("accepts a free-to-play contest with no deposit required", () => {\n  const result = evaluateCandidate("https://example.com/free-play", "Free-to-play puzzle contest cash prize", "No deposit required. Winners receive prize payout by bank transfer.");\n  if (!result.accepted) throw new Error(`Expected no-deposit contest to be accepted, got: ${result.reason}`);\n});\n\nDeno.test("accepts a prediction contest that explicitly says no wager is required", () => {
  const result = evaluateCandidate("https://example.com/no-wager-picks", "Free match prediction contest cash prize", "No wager or deposit is required. Winners receive prize payout by bank transfer.");
  if (!result.accepted) throw new Error(`Expected no-wager contest to be accepted, got: ${result.reason}`);
});
