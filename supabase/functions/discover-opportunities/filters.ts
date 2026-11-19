export type CandidateDecision =
  | { accepted: true; url: string; payoutMethods: string[] }
  | { accepted: false; reason: "invalid_url" | "excluded_category" | "missing_free_entry_evidence" | "missing_reward_evidence" | "missing_payout_evidence" };

const EXCLUDED_RESULT_RE = /\b(survey|surveys|questionnaire|microtask|micro-task|crowd.?work|freelance job|job opening|career|news|press release|blog post|article|guide|directory|archives?|roundup|review|comparison|cashback|cash back|loyalty program|rewards? program|points redemption|redeem points|affiliate referral|referral bonus|invite friends|sign.?up bonus|registration bonus|paid to register|offerwall|price chart|token price|market cap|cryptocurrency price|payment gateway|accept payments|merchant account|business payments|casino|gambling|betting|sportsbook|bookmaker|betting exchange|poker|roulette|slot machine|slot games|real.?money gaming)\b/i;
const GAME_ACTIVITY_RE = /\b(game|games|gaming|play|player|puzzle|contest|competition|tournament|sweepstakes|giveaway|raffle|lucky draw|prize draw|free draw|lottery|spin|wheel|daily spin|scratch|instant.?win|quiz|trivia|iq test|brain.?test|predict|prediction|pick.?em|match predictor|score predictor|hackathon|agentic|ai agent|agent tournament|autonomous agent)\b/i;
const REWARD_EVIDENCE_RE = /\b(cash prize|prize money|win cash|cash reward|win.{0,20}(a |the )?prize|win.{0,20}(gift card|voucher|car|phone|cash)|prize pool|(?:first|second|third) place prize|winner.{0,30}(prize|paid|reward)|paid.{0,30}winner|earn.{0,30}(cash|prize)|withdraw.{0,30}(winnings|prize|reward)|redeem.{0,20}(cash|prize)|(?:US\$|USD\s?\$?)\s?[\d,]+.{0,24}\bto\s+(?:the\s+)?winner|payout|paid in|reward.{0,20}(cash|crypto|token))\b/i;
const NO_REAL_REWARD_RE = /\b(no cash prize|no real[- ]money prize|no monetary reward|no cash value|not redeemable for cash|cannot be withdrawn|non[- ]withdrawable|points only|virtual points only|for entertainment only|gift cards?|vouchers?|store credit|merchandise|physical prizes?|non[- ]cash prizes?|(?:winner receives|win|prize.{0,20}(?:is|includes)|delivered).{0,40}(?:car|phone|tablet|laptop|computer|console|television|bike|bicycle)|(?:car|phone|tablet|laptop|computer|console|television|bike|bicycle).{0,40}(?:delivered|shipped|courier))\b/i;
const FREE_ENTRY_RE = /\b(no purchase necessary|no purchase required|free chips|free entry|free to enter|free to play|free draw|free spin|daily free spin|without paying|no entry fee|free participation|free route|no deposit required|without deposit|no wager(?: or deposit)? (?:is )?required|no stake required)\b/i;
const PAID_ENTRY_RE = /\b(pay to enter|paid entry|(?<!no )purchase required|buy (a )?(ticket|entry|credit|token)|(?<!no )entry fee|ticket price|deposit to enter|deposit.{0,24}(unlock|spin|enter|participate|play)|(?:unlock|spin|enter|participate|play).{0,24}deposit|place (a )?wager|wager required|stake required)\b/i;
const PAYOUT_CONTEXT_RE = /\b(payout|withdraw|withdrawal|cash.?out|paid to|paid by|payment method|payment processor|prize paid|winnings paid|bank transfer|bank account|bank card|debit card|credit card|via (paypal|skrill|neteller|payeer|payoneer|webmoney)|through (paypal|skrill|neteller|payeer|payoneer|webmoney)|using (paypal|skrill|neteller|payeer|payoneer|webmoney)|bitcoin|btc|usdt|crypto)\b/i;
const MONETARY_REWARD_RE = /(?:\b(cash prize|prize money|cash reward|cash winnings|paid in (?:cash|usd|eur|gbp|usdt|usdc|bitcoin)|bitcoin prize|btc prize|usdt prize|usdc prize)\b|(?:US\$|USD\s?\$?|[$€£])\s?\d[\d,.]*|\b\d[\d,.]*\s?(?:USD|EUR|GBP|USDT|USDC|BTC)\b)/i;
const SPECIFIC_PAYOUT_METHOD_RE = /\b(paypal|skrill|neteller|payeer|payoneer|webmoney|bank transfer|wire transfer|swift|bank account|bank card|debit card|credit card|visa|mastercard|bitcoin|\bbtc\b|\busdt\b|\busdc\b|ethereum|\beth\b)\b/i;

export function normalizePublicHttpsUrl(rawUrl: string): string | null {
  let parsed: URL;
  try { parsed = new URL(rawUrl); } catch { return null; }
  if (parsed.protocol !== "https:" || parsed.username || parsed.password) return null;
  if (parsed.port && parsed.port !== "443") return null;
  const host = parsed.hostname.toLowerCase().replace(/\.$/, "");
  if (!host || host === "localhost" || host.endsWith(".localhost") || host.endsWith(".local")) return null;
  if (host.startsWith("[") || /^\d{1,3}(?:\.\d{1,3}){3}$/.test(host)) return null;
  const labels = host.split(".");
  if (labels.length < 2 || labels.some(label => !label || label.length > 63 || !/^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$/.test(label))) return null;
  return parsed.toString();
}

export function canonicalOpportunityUrl(rawUrl: string): string | null {
  const normalized = normalizePublicHttpsUrl(rawUrl);
  if (!normalized) return null;
  const parsed = new URL(normalized);
  parsed.hash = "";
  for (const key of [...parsed.searchParams.keys()]) {
    const lower = key.toLowerCase();
    if (lower.startsWith("utm_") || ["gclid", "dclid", "fbclid", "msclkid", "mc_cid", "mc_eid"].includes(lower)) {
      parsed.searchParams.delete(key);
    }
  }
  parsed.searchParams.sort();
  return parsed.toString();
}

const SHORTENER_HOSTS = new Set([
  "bit.ly", "t.co", "tinyurl.com", "ow.ly", "is.gd", "buff.ly",
  "cutt.ly", "rebrand.ly", "rb.gy", "lnkd.in", "shorturl.at",
]);
const COMMON_HOSTING_SUFFIXES = [
  ".pages.dev", ".netlify.app", ".vercel.app", ".github.io",
  ".web.app", ".firebaseapp.com", ".blogspot.com", ".wordpress.com",
];

export function mergeDuplicateCandidates<T extends Record<string, unknown>>(rows: T[]): T[] {
  const grouped = new Map<string, T>();
  for (const row of rows) {
    const key = canonicalOpportunityUrl(String(row.url || ""));
    if (!key) continue;
    const current = grouped.get(key);
    if (!current) {
      grouped.set(key, { ...row, url: key });
      continue;
    }

    const merged = { ...current } as Record<string, unknown>;
    const descriptions = [...new Set([
      String(current.reward_description || "").trim(),
      String(row.reward_description || "").trim(),
    ].filter(Boolean))];
    merged.reward_description = descriptions
      .sort((a, b) => b.length - a.length)
      .join("\n\n")
      .slice(0, 1800);

    const titles = [String(current.title || ""), String(row.title || "")].sort((a, b) => b.length - a.length);
    merged.title = titles[0].slice(0, 160);

    const categories = [...new Set([
      String(current.category || "").trim(),
      String(row.category || "").trim(),
    ].filter(Boolean))];
    merged.category = categories.join(", ").slice(0, 120);

    const eligibility = [...new Set([
      String(current.eligibility || "").trim(),
      String(row.eligibility || "").trim(),
    ].filter(Boolean))];
    merged.eligibility = eligibility.join(" | ").slice(0, 1800);

    const provenance = [current, row].map((candidate) => {
      const notes = String(candidate.notes || "");
      const match = notes.match(/\[DISCOVERY PROVENANCE\]\s*([\s\S]*)$/);
      if (!match) return null;
      try {
        const value = JSON.parse(match[1]);
        return {
          search_query: String(value.search_query || ""),
          discovered_at: String(value.discovered_at || ""),
          excerpt: String(value.excerpt || ""),
        };
      } catch {
        return null;
      }
    }).filter((value): value is { search_query: string; discovered_at: string; excerpt: string } => value !== null);

    const noteSummaries = [current, row]
      .map((candidate) => String(candidate.notes || "").split("\n[DISCOVERY PROVENANCE]")[0].trim())
      .filter(Boolean);
    const baseNotes = [...new Set(noteSummaries)].join("\n---\n").slice(0, 2200);
    const queries = [...new Set(provenance.map((item) => item.search_query).filter(Boolean))];
    const excerpts = [...new Set(provenance.map((item) => item.excerpt).filter(Boolean))];
    const dates = provenance.map((item) => item.discovered_at).filter(Boolean).sort();
    merged.notes = baseNotes + (provenance.length
      ? "\n[DISCOVERY PROVENANCE]\n" + JSON.stringify({
        source: "Mwmbl search",
        search_query: queries.join(" | ").slice(0, 720),
        discovered_at: dates[0] || "",
        excerpt: excerpts.join("\n---\n").slice(0, 900),
      })
      : "");
    grouped.set(key, merged as T);
  }
  return [...grouped.values()];
}

export function domainReviewFlags(rawUrl: string): string[] {
  const normalized = normalizePublicHttpsUrl(rawUrl);
  if (!normalized) return ["invalid_public_https_url"];
  const host = new URL(normalized).hostname.toLowerCase();
  const flags: string[] = [];
  if (host.split(".").some((label) => label.startsWith("xn--"))) {
    flags.push("internationalized_or_punycode_domain");
  }
  if (SHORTENER_HOSTS.has(host)) flags.push("link_shortener_domain");
  if (COMMON_HOSTING_SUFFIXES.some((suffix) => host.endsWith(suffix))) {
    flags.push("shared_hosting_subdomain");
  }
  if (host.split(".").length >= 5) flags.push("deep_subdomain");
  return flags;
}

export function candidateReviewFlags(title: string, description: string): string[] {
  const text = [title, description].join(" ");
  const flags: string[] = [];
  if (/\b(kyc|know your customer|identity verification|government[- ]issued id|proof of identity)\b/i.test(text)) flags.push("identity_verification_mentioned");
  if (/\b(not available|restricted|excluded|ineligible|prohibited)\b.{0,50}\b(countr(?:y|ies)|region|jurisdiction|territor(?:y|ies))\b|\b(countr(?:y|ies)|region|jurisdiction)\b.{0,50}\b(not available|restricted|excluded|ineligible|prohibited)\b/i.test(text)) flags.push("geographic_restrictions_mentioned_review_country_rules");
  if (!/\b(minimum withdrawal|minimum payout|minimum cash.?out|withdrawal threshold|cash.?out threshold)\b/i.test(text)) flags.push("minimum_withdrawal_not_found");
  if (!/\b(paypal|skrill|neteller|payeer|payoneer|webmoney|bank transfer|bank account|bank card|debit card|credit card|bitcoin|\bbtc\b|\busdt\b|\busdc\b|ethereum|\beth\b)\b/i.test(text)) flags.push("specific_payout_method_not_found");
  if (!/\b(withdrawal fee|payout fee|cash.?out fee|no (?:withdrawal |payout |cash.?out )?fees|free withdrawal|fee-free)\b/i.test(text)) flags.push("withdrawal_fees_not_found");
  const prizeAmountPattern = /(?:\b(?:prize|reward|award|winnings?|jackpot|prize pool)\b[^.!?]{0,45}(?:[$€£]\s?\d[\d,.]*|\b\d[\d,]*(?:\.\d+)?\s?(?:USD|USDT|USDC|EUR|GBP)\b)|(?:[$€£]\s?\d[\d,.]*|\b\d[\d,]*(?:\.\d+)?\s?(?:USD|USDT|USDC|EUR|GBP)\b)[^.!?]{0,30}\b(?:prize|reward|award|winnings?|jackpot)\b)/i;
  if (!prizeAmountPattern.test(text)) flags.push("prize_amount_not_found");
  if (!/\b(within\s+\d+\s+(?:business\s+)?days|paid\s+within|payment\s+(?:will|is)\s+be\s+(?:made|sent)|prize\s+(?:will|is)\s+be\s+paid)\b/i.test(text)) flags.push("payout_timing_not_found");
  if (!/\b(?:sponsor|organizer|organiser|operator|host)\s*:\s*\S+|\b(?:sponsored|organized|organised|operated|hosted)\s+by\s+[a-z0-9][a-z0-9 &.-]{2,}/i.test(text)) flags.push("organizer_identity_not_found");
  if (!/\b(winners?\s+(?:is|are|will be|selected|chosen)|selected by|judged|highest score|leaderboard|random drawing|randomly selected)\b/i.test(text)) flags.push("winner_selection_method_not_found");
  return flags;
}

export function evaluateCandidate(rawUrl: string, title: string, description: string): CandidateDecision {
  const normalizedUrl = normalizePublicHttpsUrl(rawUrl);
  if (!normalizedUrl) return { accepted: false, reason: "invalid_url" };

  const text = [title, description, rawUrl].join(" ");
  const host = new URL(normalizedUrl).hostname.toLowerCase();
  // Zoa Agent Season references are trusted only on the exact official host.
  // Reject lookalike domains before the general prize-game rules can accept them.
  const mentionsZoaAgentSeason = /zoa(?:games)?/i.test(text) && /agent season 1/i.test(text);
  if (mentionsZoaAgentSeason && host !== "play.zoagames.com") {
    return { accepted: false, reason: "excluded_category" };
  }
  // Narrow exception: Zoa's official agent ladder uses free, non-purchasable chips;
  // candidates still enter the ordinary "discovered" review queue, never auto-play.
  const verifiedZoaAgentSeason = host === "play.zoagames.com"
    && /agent season 1/i.test(text)
    && /free chips|agents play free/i.test(text)
    && /\$490|490 usdc/i.test(text);
  if ((EXCLUDED_RESULT_RE.test(text) && !verifiedZoaAgentSeason) || !GAME_ACTIVITY_RE.test(text)) {
    return { accepted: false, reason: "excluded_category" };
  }

  // Paid-entry language is rejected even if a page also mentions a free route.
  // Dual-route promotions need manual verification of the genuine free route.
  if (PAID_ENTRY_RE.test(text)) {
    return { accepted: false, reason: "excluded_category" };
  }

  if (!FREE_ENTRY_RE.test(text)) return { accepted: false, reason: "missing_free_entry_evidence" };
  // Reject misleading promotional language even when payout keywords appear elsewhere.
  if (NO_REAL_REWARD_RE.test(text)) return { accepted: false, reason: "missing_reward_evidence" };
  if (!REWARD_EVIDENCE_RE.test(text) || !MONETARY_REWARD_RE.test(text)) return { accepted: false, reason: "missing_reward_evidence" };
  if (!PAYOUT_CONTEXT_RE.test(text) || !SPECIFIC_PAYOUT_METHOD_RE.test(text)) return { accepted: false, reason: "missing_payout_evidence" };

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
  return { accepted: true, url: normalizedUrl, payoutMethods };
}
