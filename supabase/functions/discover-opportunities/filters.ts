export type CandidateDecision =
  | { accepted: true; url: string; payoutMethods: string[] }
  | { accepted: false; reason: "invalid_url" | "excluded_category" | "missing_free_entry_evidence" | "missing_reward_evidence" | "missing_payout_evidence" };

const EXCLUDED_RESULT_RE = /\b(survey|surveys|questionnaire|microtask|micro-task|crowd.?work|freelance job|job opening|career|news|press release|blog post|article|guide|directory|archives?|roundup|review|comparison|cashback|cash back|loyalty program|rewards? program|points redemption|redeem points|affiliate referral|referral bonus|invite friends|sign.?up bonus|registration bonus|paid to register|offerwall|price chart|token price|market cap|cryptocurrency price|payment gateway|accept payments|merchant account|business payments|casino|betting|sportsbook|slot machine)\b/i;
const GAME_ACTIVITY_RE = /\b(game|games|gaming|play|player|puzzle|contest|competition|tournament|sweepstakes|giveaway|raffle|lucky draw|prize draw|free draw|lottery|spin|wheel|daily spin|scratch|instant.?win|quiz|trivia|iq test|brain.?test|predict|prediction|pick.?em|match predictor|score predictor)\b/i;
const REWARD_EVIDENCE_RE = /\b(cash prize|prize money|win cash|cash reward|win.{0,20}(a |the )?prize|win.{0,20}(gift card|voucher|car|phone|cash)|prize pool|winner.{0,30}(prize|paid|reward)|paid.{0,30}winner|earn.{0,30}(cash|prize)|withdraw.{0,30}(winnings|prize|reward)|redeem.{0,20}(cash|prize)|payout|paid in|reward.{0,20}(cash|crypto|token))\b/i;
const FREE_ENTRY_RE = /\b(no purchase necessary|no purchase required|free entry|free to enter|free to play|free draw|free spin|daily free spin|without paying|no entry fee|free participation|free route|no deposit required|without deposit|no wager(?: or deposit)? (?:is )?required|no stake required)\b/i;
const PAID_ENTRY_RE = /\b(pay to enter|paid entry|(?<!no )purchase required|buy (a )?(ticket|entry)|(?<!no )entry fee|ticket price|deposit to enter|place (a )?wager|wager required|stake required)\b/i;
const PAYOUT_CONTEXT_RE = /\b(payout|withdraw|withdrawal|cash.?out|paid to|paid by|payment method|prize paid|winnings paid|bank transfer|bank account|bank card|debit card|credit card|via (paypal|skrill|neteller|payeer|payoneer|webmoney)|through (paypal|skrill|neteller|payeer|payoneer|webmoney)|using (paypal|skrill|neteller|payeer|payoneer|webmoney)|bitcoin|btc|usdt|crypto)\b/i;

export function evaluateCandidate(rawUrl: string, title: string, description: string): CandidateDecision {
  let parsed: URL;
  try { parsed = new URL(rawUrl); } catch {
    return { accepted: false, reason: "invalid_url" };
  }
  if (parsed.protocol !== "https:") return { accepted: false, reason: "invalid_url" };

  const text = [title, description, rawUrl].join(" ");
  if (EXCLUDED_RESULT_RE.test(text) || !GAME_ACTIVITY_RE.test(text)) {
    return { accepted: false, reason: "excluded_category" };
  }

  // Paid-entry language is rejected even if a page also mentions a free route.
  // Dual-route promotions need manual verification of the genuine free route.
  if (PAID_ENTRY_RE.test(text)) {
    return { accepted: false, reason: "excluded_category" };
  }

  if (!REWARD_EVIDENCE_RE.test(text)) return { accepted: false, reason: "missing_reward_evidence" };
  if (!PAYOUT_CONTEXT_RE.test(text)) return { accepted: false, reason: "missing_payout_evidence" };

  const lower = text.toLowerCase();
  const payoutMethods = [
    /\bpaypal\b/.test(lower) ? "PayPal" : null,
    /\bskrill\b/.test(lower) ? "Skrill" : null,
    /\bneteller\b/.test(lower) ? "Neteller" : null,
    /\bpayeer\b/.test(lower) ? "Payeer" : null,
    /\bpayoneer\b/.test(lower) ? "Payoneer" : null,
    /\bwebmoney\b/.test(lower) ? "WebMoney" : null,
    /\b(bank transfer|bank account)\b/.test(lower) ? "Bank transfer" : null,
    /\b(bank card|debit card|credit card|visa|mastercard)\b/.test(lower) ? "Bank card" : null,
    /bitcoin|\bbtc\b|\busdt\b|ethereum|\beth\b|crypto|cryptocurrency|tether|\busdc\b/.test(lower) ? "Crypto" : null,
  ].filter((value): value is string => Boolean(value));
  return { accepted: true, url: parsed.toString(), payoutMethods };
}
