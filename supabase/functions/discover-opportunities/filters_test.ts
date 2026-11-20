import { assertEquals } from "jsr:@std/assert";
import { candidateReviewFlags, canonicalOpportunityUrl, domainReviewFlags, evaluateCandidate, mergeDuplicateCandidates, normalizePublicHttpsUrl, MAX_SEARCH_RESPONSE_BYTES, readBoundedSearchResponse, parseBoundedSearchResponse } from "./filters.ts";

function assertRejected(url: string, title: string, description: string, reason: string) {
  const result = evaluateCandidate(url, title, description);
  if (result.accepted) throw new Error(`Expected rejection: ${reason}`);
  assertEquals(result.reason, reason);
}

Deno.test("rejects survey even when it mentions PayPal", () => assertRejected("https://example.com/survey", "Paid survey", "Earn PayPal rewards", "excluded_category"));
Deno.test("rejects paid-click, ad-viewing, and micro-gig offers even with cash payout wording", () => {
  for (const [path, title, description] of [
    ["/click", "Paid to click cash reward", "Free entry. Click ads to earn cash prize paid by PayPal."],
    ["/ads", "Watch video ads for cash", "Free to play. Watch video ads and withdraw cash by Skrill."],
    ["/tasks", "Micro jobs task platform", "Free registration. Complete data entry tasks for cash payout by bank transfer."],
    ["/apps", "Paid app testing offers", "Free entry. Test apps and receive cash reward via PayPal."],
  ]) {
    assertRejected("https://example.com" + path, title, description, "excluded_category");
  }
});
Deno.test("rejects referral signup bonus", () => assertRejected("https://example.com", "Invite friends", "PayPal signup bonus", "excluded_category"));
Deno.test("rejects non-HTTPS URLs", () => assertRejected("http://example.com", "Prize game", "PayPal rewards", "invalid_url"));
Deno.test("accepts a game candidate when search snippets omit payout details", () => {
  const result = evaluateCandidate("https://example.com/game", "Puzzle contest cash prize", "Winners receive payout after withdrawal request.");
  if (!result.accepted) throw new Error(`Expected manual-access approval, got: ${result.reason}`);
  assertEquals(result.payoutMethods, []);
});
Deno.test("rejects a PayPal payment page surfaced by game search", () => assertRejected("https://paypal.com/business", "PayPal Payment Options for Global Businesses", "Merchant deals and cashback rewards", "excluded_category"));
Deno.test("rejects generic loyalty points", () => assertRejected("https://example.com/rewards", "Redeeming PayPal Rewards points", "Donate points to a cause", "excluded_category"));
Deno.test("rejects editorial play-to-earn directories", () => assertRejected("https://example.com/archive", "Play to earn games archives", "Latest news and best games to watch", "excluded_category"));
Deno.test("rejects token price pages even when game token named", () => assertRejected("https://coindesk.com/price/play", "PLAY price chart", "Gaming token price, market cap and crypto", "excluded_category"));
Deno.test("accepts game pages when search snippets omit prize details", () => {
  const result = evaluateCandidate("https://example.com/game", "Free online puzzle game", "Play now with PayPal available");
  if (!result.accepted) throw new Error(`Expected manual-access approval, got: ${result.reason}`);
});
Deno.test("accepts prize games when payout context is not present in the snippet", () => {
  const result = evaluateCandidate("https://example.com/game", "Puzzle contest cash prize", "Win cash and prizes. PayPal mentioned.");
  if (!result.accepted) throw new Error(`Expected manual-access approval, got: ${result.reason}`);
});
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
  const result = evaluateCandidate("https://example.com/raffle", "Free raffle prize draw cash prize", "Free entry, no purchase required. Prize paid to winners by bank card.");
  if (!result.accepted) throw new Error(`Expected free raffle to be accepted, got: ${result.reason}`);
  assertEquals(result.payoutMethods, ["Bank card"]);
  assertEquals(result.url, "https://example.com/raffle");
});
Deno.test("rejects a free sweepstakes whose only prize is a gift card", () => {
  assertRejected("https://example.com/sweepstakes", "Free sweepstakes win a gift card", "No purchase necessary. Prize payout is delivered by Visa gift card.", "excluded_category");
});
Deno.test("rejects a free draw whose only prize is physical merchandise", () => {
  assertRejected("https://example.com/draw", "Free prize draw win a phone", "No purchase necessary. Winner receives a new phone delivered by courier.", "missing_reward_evidence");
});
Deno.test("rejects a paid raffle with no free entry route", () => {
  assertRejected("https://example.com/raffle", "Paid raffle win a car", "Buy a ticket, entry fee required. Prize paid by bank transfer.", "excluded_category");
});
Deno.test("rejects a spin wheel with no real prize or payout evidence", () => {
  assertRejected("https://example.com/wheel", "Free lucky spin wheel game", "Free entry. Spin for fun and collect points.", "missing_reward_evidence");
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

Deno.test("accepts a prize game when free-entry details are absent from the snippet", () => {
  const result = evaluateCandidate("https://example.com/game", "Online game cash prize", "Winners receive cash prize payout by bank transfer.");
  if (!result.accepted) throw new Error(`Expected manual-access approval, got: ${result.reason}`);
});

Deno.test("accepts a free-to-play contest with no deposit required", () => {
  const result = evaluateCandidate("https://example.com/free-play", "Free-to-play puzzle contest cash prize", "No deposit required. Winners receive prize payout by bank transfer.");
  if (!result.accepted) throw new Error(`Expected no-deposit contest to be accepted, got: ${result.reason}`);
});

Deno.test("accepts a prediction contest that explicitly says no wager is required", () => {
  const result = evaluateCandidate("https://example.com/no-wager-picks", "Free match prediction contest cash prize", "No wager or deposit is required. Winners receive prize payout by bank transfer.");
  if (!result.accepted) throw new Error(`Expected no-wager contest to be accepted, got: ${result.reason}`);
});

Deno.test("accepts a free lottery-style prize draw with no purchase and a real payout", () => {
  const result = evaluateCandidate("https://example.com/lottery", "Free online lottery prize draw", "No purchase necessary. Free entry. Winners receive a cash prize paid by bank transfer.");
  if (!result.accepted) throw new Error(`Expected free prize draw to be accepted, got: ${result.reason}`);
  assertEquals(result.payoutMethods, ["Bank transfer"]);
});

Deno.test("rejects a paid lottery ticket that requires payment", () => {
  assertRejected("https://example.com/lottery-ticket", "Lottery ticket cash prize", "Buy a ticket. Ticket price $5. Winners receive cash prize payout by bank transfer.", "excluded_category");
});

Deno.test("keeps a free raffle with official no-purchase language eligible for review", () => {
  const result = evaluateCandidate("https://example.com/free-raffle", "Free raffle prize draw cash prize", "No purchase necessary. Free entry. Winners receive prize payout by bank transfer.");
  if (!result.accepted) throw new Error(`Expected free raffle to remain a candidate, got: ${result.reason}`);
});

Deno.test("rejects credentialed, local, IP literal and non-standard-port URLs", () => {
  for (const url of [
    "https://user:pass@example.com/game",
    "https://localhost/game",
    "https://service.local/game",
    "https://metadata.google.internal/game",
    "https://staging.test/game",
    "https://example.invalid/game",
    "https://example.example/game",
    "https://127.0.0.1/game",
    "https://192.168.1.10/game",
    "https://[::1]/game",
    "https://example.com:8443/game",
  ]) assertEquals(normalizePublicHttpsUrl(url), null);
});
Deno.test("normalizes a public HTTPS URL and permits the default HTTPS port", () => {
  assertEquals(normalizePublicHttpsUrl("https://Example.com:443/game"), "https://example.com/game");
});

Deno.test("canonicalizes tracking parameters and fragments for duplicate detection", () => {
  assertEquals(
    canonicalOpportunityUrl("https://Example.com/game?utm_source=newsletter&level=2#top"),
    "https://example.com/game?level=2",
  );
});
Deno.test("preserves functional query parameters while sorting them", () => {
  assertEquals(
    canonicalOpportunityUrl("https://example.com/game?z=9&level=2&a=1"),
    "https://example.com/game?a=1&level=2&z=9",
  );
});
Deno.test("rejects unsafe URLs during canonicalization", () => {
  assertEquals(canonicalOpportunityUrl("http://example.com/game?utm_source=x"), null);
});

Deno.test("flags link shorteners for manual destination verification", () => {
  assertEquals(domainReviewFlags("https://bit.ly/3abc"), ["official_source_not_verified", "link_shortener_domain"]);
});
Deno.test("flags shared hosting without automatically rejecting the candidate", () => {
  assertEquals(domainReviewFlags("https://promo.netlify.app/game"), ["official_source_not_verified", "shared_hosting_subdomain"]);
});
Deno.test("flags punycode and unusually deep subdomains", () => {
  assertEquals(
    domainReviewFlags("https://xn--e1afmkfd.xn--p1ai.a.b.example.com/game"),
    ["official_source_not_verified", "internationalized_or_punycode_domain", "deep_subdomain"],
  );
});
Deno.test("ordinary HTTPS domains are still explicitly marked as not officially verified", () => {
  assertEquals(domainReviewFlags("https://example.com/game"), ["official_source_not_verified"]);
});
Deno.test("rejects a wheel game that requires a deposit", () => {
  assertRejected("https://example.com/wheel", "Lucky wheel cash prize", "Deposit $5 to unlock daily spins. Winners receive payout by PayPal.", "excluded_category");
});
Deno.test("rejects a free spin claim without verifiable prize payout context", () => {
  assertRejected("https://example.com/spin", "Daily free spin wheel", "Spin for fun and collect points. No withdrawal information is provided.", "missing_reward_evidence");
});
Deno.test("accepts free instant-win promotion only with prize and payout evidence", () => {
  const result = evaluateCandidate("https://example.com/instant-win", "Free instant win cash prize", "No purchase necessary. Winner receives prize payout by bank transfer under official rules.");
  if (!result.accepted) throw new Error(`Expected acceptance, got: ${result.reason}`);
  assertEquals(result.payoutMethods, ["Bank transfer"]);
});

Deno.test("rejects promotional copy that explicitly says there is no cash prize", () => {
  assertRejected("https://example.com/spin", "Free spin cash prize promotion", "No purchase necessary. No cash prize is offered; collect points only.", "missing_reward_evidence");
});
Deno.test("rejects points that cannot be withdrawn even when payout keywords appear", () => {
  assertRejected("https://example.com/game", "Free puzzle game cash reward", "Free entry. Points only, cannot be withdrawn. Payout information is not applicable.", "missing_reward_evidence");
});
Deno.test("rejects entertainment-only games that use misleading prize wording", () => {
  assertRejected("https://example.com/wheel", "Lucky wheel win cash prize", "Free spin for entertainment only. No monetary reward.", "missing_reward_evidence");
});

Deno.test("rejects cash-prize wording contradicted by no-cash-value terms", () => {
  assertRejected("https://example.com/promo", "Free game win cash prize", "No purchase necessary. The advertised prize has no cash value and cannot be redeemed for cash. Winners receive payout details by PayPal.", "missing_reward_evidence");
});
Deno.test("rejects non-withdrawable virtual tokens despite withdrawal keywords", () => {
  assertRejected("https://example.com/tokens", "Free puzzle game cash reward", "Free entry. Virtual points only; rewards are non-withdrawable. Withdrawal and payout are not supported.", "missing_reward_evidence");
});
Deno.test("rejects entertainment-only spin promotions with misleading winner payout text", () => {
  assertRejected("https://example.com/spin", "Daily free spin win cash prize", "Free spin for entertainment only. No monetary reward is provided, although the page describes a payout process.", "missing_reward_evidence");
});


Deno.test("country restrictions are not used as a discovery filter", () => {
  const result = evaluateCandidate("https://example.com/game", "Free game with cash prize", "No purchase necessary. Winner receives payout by PayPal. Not available in Iran.");
  if (!result.accepted) throw new Error(`Country wording must not filter discovery, got: ${result.reason}`);
});

Deno.test("discovers the official fmsg free autonomous-agent puzzle hackathon with SWIFT cash prize", () => {
  const result = evaluateCandidate(
    "https://fmsg.ai/hackathon",
    "Hackathon — Any AI agent. Anywhere in the world.",
    "US$5,003 to the winner. Free to enter. Any AI agent, on any model, running anywhere. The game runs from 09:00 UTC on 28 November 2026 until the puzzle is solved. One prize is paid by international bank transfer (SWIFT)."
  );
  if (!result.accepted) throw new Error(`Expected official fmsg agent puzzle contest to pass discovery, got: ${result.reason}`);
  assertEquals(result.payoutMethods, ["Bank transfer"]);
});

Deno.test("rejects AI-agent prize claims with only a generic payment processor", () => {
  assertRejected(
    "https://example.com/agent-tournament",
    "Agentic AI agent tournament",
    "No entry fee. Autonomous AI agents compete for first place prize of $500. Prizes are paid through a third-party payment processor.",
    "missing_payout_evidence",
  );
});

Deno.test("holds AI-agent contest with unnamed payment processor for manual discovery review", () => {
  assertRejected(
    "https://agenticworldcup.ai/rules",
    "Agentic World Cup official contest rules",
    "NO ENTRY FEE. First Place Prize: $500 (US). Second Place Prize: $300 (US). Third Place Prize: $200 (US). All prize payments are subject to the ability of Sponsor's third-party payment processor to process payment to the winner.",
    "missing_payout_evidence",
  );
});

Deno.test("discovers Zoa agent season only with official host, free chips, and prize evidence", () => {
  const result = evaluateCandidate(
    "https://play.zoagames.com/agent-docs",
    "Zoa Agent Season 1 autonomous agent ladder",
    "Agents play free with free chips. Agent Season 1 has a $490 USDC prize pool, paid to the verified human owner after five completed challenge matches."
  );
  if (!result.accepted) throw new Error(`Expected official Zoa free-chip agent season to pass discovery, got: ${result.reason}`);
});
Deno.test("does not allow unrelated betting sites through the Zoa exception", () => {
  assertRejected(
    "https://example.com/agent-docs",
    "Agent Season 1 betting game for agents",
    "Agents play free with free chips. Agent Season 1 has a $490 USDC prize pool.",
    "excluded_category"
  );
});

Deno.test("rejects gambling sites even when they advertise free entry and payouts", () => {
  assertRejected("https://example.com/predictions", "Free football prediction contest cash prize", "Free entry. Gambling platform with cash payout and optional play.", "excluded_category");
});
Deno.test("rejects bookmaker and betting exchange results", () => {
  assertRejected("https://example.com/picks", "Free match prediction contest prize money", "No purchase necessary. Bookmaker offers betting exchange markets and cash payouts.", "excluded_category");
});
Deno.test("rejects poker and roulette promotions", () => {
  assertRejected("https://example.com/casino", "Free poker tournament cash prize", "Free entry. Poker and roulette games with cash prize payout by bank transfer.", "excluded_category");
});

Deno.test("recognizes the official Zoa Agent Season prize when the amount uses a dollar sign", () => {
  const result = evaluateCandidate(
    "https://play.zoagames.com/agent-docs/season-1",
    "AI agent Agent Season 1 game",
    "Agents play free with free chips. Agent Season 1 prize pool is $490 USDC with payout to the winner.",
  );
  if (!result.accepted) throw new Error("Expected official Zoa season candidate to be accepted, got: " + result.reason);
  assertEquals(result.payoutMethods, ["Crypto"]);
});

Deno.test("does not extend the Zoa exception to lookalike hosts", () => {
  assertRejected(
    "https://play.zoagames.com.attacker.example/agent-docs/season-1",
    "AI agent Agent Season 1 game",
    "Agents play free with free chips. Agent Season 1 prize pool is $490 USDC with payout to the winner.",
    "invalid_url",
  );
});

Deno.test("auto-approves eligible game candidates when free-entry evidence is missing", () => {
  const result = evaluateCandidate(
    "https://play.zoagames.com/agent-docs/season-1",
    "AI agent Agent Season 1 game",
    "Agent Season 1 prize pool is $490 USDC with payout to the winner.",
  );
  if (!result.accepted) throw new Error(`Expected manual-access approval, got: ${result.reason}`);
});

Deno.test("rejects Zoa Agent Season candidates that require a deposit", () => {
  assertRejected(
    "https://play.zoagames.com/agent-docs/season-1",
    "AI agent Agent Season 1 game",
    "Agents play free with free chips. Agent Season 1 prize pool is $490 USDC with payout to the winner. Deposit to enter.",
    "excluded_category",
  );
});


Deno.test("surfaces due-diligence gaps without filtering country-restricted candidates", () => {
  const flags = candidateReviewFlags("Free puzzle cash prize", "No purchase necessary. Winner receives payout through a third-party payment processor. KYC identity verification may be required. Not available in some countries.");
  assertEquals(flags, [
    "official_terms_source_not_verified",
    "identity_verification_mentioned",
    "geographic_restrictions_mentioned_review_country_rules",
    "minimum_withdrawal_not_found",
    "specific_payout_method_not_found",
    "withdrawal_fees_not_found",
    "prize_amount_not_found",
    "payout_timing_not_found",
    "organizer_identity_not_found",
    "winner_selection_method_not_found",
  ]);
});

Deno.test("flags missing prize amount, payout timing, organizer identity and winner selection", () => {
  assertEquals(
    candidateReviewFlags("Free puzzle cash prize", "No purchase necessary. Winner receives payout through PayPal. Minimum withdrawal is 10 USD. No withdrawal fees."),
    ["official_terms_source_not_verified", "prize_amount_not_found", "payout_timing_not_found", "organizer_identity_not_found", "winner_selection_method_not_found"],
  );
});

Deno.test("does not mistake a minimum withdrawal amount for a prize amount", () => {
  const flags = candidateReviewFlags(
    "Free cash contest",
    "Minimum withdrawal is $10. PayPal payout available. No withdrawal fees.",
  );
  assertEquals(flags.includes("prize_amount_not_found"), true);
});

Deno.test("recognizes a prize amount when explicitly tied to a prize label", () => {
  const flags = candidateReviewFlags(
    "Free cash contest",
    "Prize: $250 USD. Minimum withdrawal is $10. PayPal payout available. No withdrawal fees.",
  );
  assertEquals(flags.includes("prize_amount_not_found"), false);
});

Deno.test("does not flag disclosed prize, payout timing, organizer and winner selection terms", () => {
  assertEquals(
    candidateReviewFlags("Free cash prize contest", "Sponsor: Example Games. Prize is $500 USD. Winners are selected by highest score. Payment will be made within 30 days via PayPal. Minimum withdrawal is 10 USD. No withdrawal fees. No purchase necessary."),
    ["official_terms_source_not_verified"],
  );
});


Deno.test("merges duplicate discovery URLs and preserves distinct search provenance", () => {
  const merged = mergeDuplicateCandidates([
    {
      url: "https://example.com/game?utm_source=one",
      title: "Free puzzle game",
      category: "game",
      reward_description: "Prize: $100. Free entry.",
      eligibility: "Payout method hints: PayPal. Due-diligence flags: fees missing.",
      notes: "Review the official terms.\n[DISCOVERY PROVENANCE]\n" + JSON.stringify({
        source: "Mwmbl search", search_query: "free puzzle prize", discovered_at: "2026-11-19T10:00:00.000Z", excerpt: "Prize: $100.",
      }),
    },
    {
      url: "https://example.com/game?utm_source=two",
      title: "Free puzzle game official contest",
      category: "contest",
      reward_description: "Winners receive $100 payout within 30 days.",
      eligibility: "Payout method hints: Skrill. Due-diligence flags: organizer missing.",
      notes: "Other notes.\n[DISCOVERY PROVENANCE]\n" + JSON.stringify({
        source: "Mwmbl search", search_query: "official contest payout", discovered_at: "2026-11-19T11:00:00.000Z", excerpt: "Payout within 30 days.",
      }),
    },
  ]);
  assertEquals(merged.length, 1);
  assertEquals(merged[0].url, "https://example.com/game");
  assertEquals(merged[0].title, "Free puzzle game official contest");
  assertEquals(merged[0].category, "game, contest");
  assertEquals(String(merged[0].notes).includes("Other notes."), true);
  assertEquals(String(merged[0].notes).includes("Review the official terms."), true);
  assertEquals(String(merged[0].reward_description).includes("Prize: $100."), true);
  assertEquals(String(merged[0].reward_description).includes("Winners receive $100 payout"), true);
  assertEquals(String(merged[0].eligibility).includes("PayPal"), true);
  assertEquals(String(merged[0].eligibility).includes("Skrill"), true);
  const notes = String(merged[0].notes);
  const provenance = JSON.parse(notes.split("[DISCOVERY PROVENANCE]\n")[1]);
  assertEquals(provenance.search_query, "free puzzle prize | official contest payout");
  assertEquals(provenance.excerpt.includes("Prize: $100."), true);
  assertEquals(provenance.excerpt.includes("Payout within 30 days."), true);
});

Deno.test("ignores invalid candidate URLs and preserves notes with malformed provenance", () => {
  const merged = mergeDuplicateCandidates([
    { url: "javascript:alert(1)", title: "Unsafe URL", notes: "must be discarded" },
    { url: "https://example.com/safe", title: "Safe candidate", notes: "Owner note.\n[DISCOVERY PROVENANCE]\n{not-json}" },
  ]);
  assertEquals(merged.length, 1);
  assertEquals(merged[0].url, "https://example.com/safe");
  assertEquals(String(merged[0].notes).includes("Owner note."), true);
  assertEquals(String(merged[0].notes).includes("{not-json}"), true);
});

Deno.test("does not merge candidates with different functional URL parameters", () => {
  const merged = mergeDuplicateCandidates([
    { url: "https://example.com/game?level=1", title: "Level one" },
    { url: "https://example.com/game?level=2", title: "Level two" },
  ]);
  assertEquals(merged.length, 2);
});

Deno.test("bounds untrusted search response streams before JSON parsing", async () => {
  const valid = await readBoundedSearchResponse(new Response('{"ok":true}'));
  assertEquals(parseBoundedSearchResponse(valid), { ok: true });
  const oversized = new Response(new Uint8Array(MAX_SEARCH_RESPONSE_BYTES + 1));
  let rejected = false;
  try { await readBoundedSearchResponse(oversized); }
  catch (error) { rejected = String(error).includes("1 MB processing limit"); }
  assertEquals(rejected, true);
});

Deno.test("rejects malformed bounded search JSON", () => {
  let rejected = false;
  try { parseBoundedSearchResponse("{not-json}"); } catch { rejected = true; }
  assertEquals(rejected, true);
});


Deno.test("duplicate discovery candidates retain merged provenance without implying official verification", () => {
  const provenance = (query: string, excerpt: string) =>
    "[DISCOVERY PROVENANCE]\n" + JSON.stringify({
      source: "Mwmbl search",
      search_query: query,
      discovered_at: "2026-11-20T08:00:00.000Z",
      excerpt,
    });
  const merged = mergeDuplicateCandidates([
    {
      url: "https://example.com/contest?utm_source=one#top",
      title: "Free puzzle cash prize",
      reward_description: "Cash prize paid by Skrill",
      notes: "Due-diligence flags: official_source_not_verified.\n" + provenance("free puzzle prize", "Search result A"),
    },
    {
      url: "https://example.com/contest?utm_campaign=two",
      title: "Puzzle contest with cash reward",
      reward_description: "Winners receive payout by Skrill",
      notes: "Due-diligence flags: official_terms_source_not_verified.\n" + provenance("cash reward puzzle", "Search result B"),
    },
  ]);
  assertEquals(merged.length, 1);
  assertEquals(merged[0].url, "https://example.com/contest");
  const mergedNotes = String(merged[0].notes);
  assertEquals(mergedNotes.includes("free puzzle prize"), true);
  assertEquals(mergedNotes.includes("cash reward puzzle"), true);
  assertEquals(mergedNotes.includes("Search result A"), true);
  assertEquals(mergedNotes.includes("Search result B"), true);
  assertEquals(mergedNotes.includes("official_source_not_verified"), true);
  assertEquals(mergedNotes.includes("official_terms_source_not_verified"), true);
});
