export type CandidateDecision =
  | { accepted: true; url: string; wallets: string[] }
  | { accepted: false; reason: "invalid_url" | "excluded_category" | "no_accepted_wallet" };

// Exclude non-game earning categories and editorial/listing pages even when they mention a supported wallet.
const EXCLUDED_RESULT_RE = /\b(survey|surveys|questionnaire|microtask|micro-task|crowd.?work|freelance job|job opening|career|news|press release|blog post|article|guide|directory|archives?|roundup|review|comparison|cashback|cash back|loyalty program|rewards? program|points redemption|redeem points|affiliate referral|referral bonus|invite friends|sign.?up bonus|registration bonus|paid to register|offerwall)\b/i;
const GAME_ACTIVITY_RE = /\b(game|games|gaming|play|player|puzzle|contest|competition|tournament|sweepstakes|giveaway|spin|wheel|scratch|instant.?win|quiz|trivia|iq test|brain.?test)\b/i;

export function evaluateCandidate(rawUrl: string, title: string, description: string): CandidateDecision {
  let parsed: URL;
  try {
    parsed = new URL(rawUrl);
  } catch {
    return { accepted: false, reason: "invalid_url" };
  }
  if (parsed.protocol !== "https:") return { accepted: false, reason: "invalid_url" };

  const text = `${title} ${description} ${rawUrl}`;
  if (EXCLUDED_RESULT_RE.test(text) || !GAME_ACTIVITY_RE.test(text)) {
    return { accepted: false, reason: "excluded_category" };
  }

  const lower = text.toLowerCase();
  const wallets = [
    /\bpaypal\b/.test(lower) ? "PayPal" : null,
    /\bskrill\b/.test(lower) ? "Skrill" : null,
    /\bneteller\b/.test(lower) ? "Neteller" : null,
    /\bpayeer\b/.test(lower) ? "Payeer" : null,
    /\bpayoneer\b/.test(lower) ? "Payoneer" : null,
    /\bwebmoney\b/.test(lower) ? "WebMoney" : null,
    /bitcoin|\bbtc\b|\busdt\b|ethereum|\beth\b|crypto|cryptocurrency|tether|\busdc\b/.test(lower) ? "Crypto" : null,
  ].filter((value): value is string => Boolean(value));

  if (!wallets.length) return { accepted: false, reason: "no_accepted_wallet" };
  return { accepted: true, url: parsed.toString(), wallets };
}
