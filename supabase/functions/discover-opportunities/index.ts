import { withSupabase } from "npm:@supabase/server@^1";
import { candidateReviewFlags, canonicalOpportunityUrl, domainReviewFlags, evaluateCandidate, mergeDuplicateCandidates, readBoundedSearchResponse, parseBoundedSearchResponse } from "./filters.ts";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

const SEARCHES = [
  { category: "game", query: "free-to-play online skill games cash prizes payout no entry fee" },
  { category: "game", query: "online game tournaments real prize money payout free entry official rules" },
  { category: "game", query: "AI agent games competition cash prizes free entry autonomous gameplay official rules" },
  { category: "game", query: "agentic game tournament autonomous AI agents prize pool no entry fee" },
  { category: "game", query: "AI agent soccer championship cash prizes free entry official contest rules" },
  { category: "game", query: 'site:play.zoagames.com/agent-docs "Agent Season 1" "$490" USDC free agent game' },
  { category: "game", query: "free online puzzle contest cash prize payout bank transfer" },
  { category: "game", query: "free games real cash prize payment method withdrawal terms" },
  { category: "sweepstakes", query: "free sweepstakes prize draw cash prize payout no purchase necessary" },
  { category: "sweepstakes", query: "online prize draw cash prize payment method free entry official rules" },
  { category: "sweepstakes", query: "crypto prize giveaway bitcoin usdt free entry official rules" },
  { category: "wheel", query: "daily free spin wheel cash prize no purchase necessary payout" },
  { category: "wheel", query: "official brand promotion spin wheel win cash prize free entry rules" },
  { category: "wheel", query: "free scratch and win instant prize official promotion no entry fee" },
  { category: "wheel", query: "free lucky wheel game cash prize winners payout official terms" },
  { category: "raffle", query: "free online raffle prize draw cash prize no purchase necessary" },
  { category: "raffle", query: "free lucky draw win prizes official rules no entry fee" },
  { category: "raffle", query: "free lottery prize draw no purchase necessary cash payout official rules" },
  { category: "prediction", query: "free sports prediction contest cash prize no wager no deposit official rules" },
  { category: "prediction", query: "free football match predictor competition prize payout no entry fee" },
  { category: "prediction", query: "free basketball cricket esports score prediction contest prizes" },
  { category: "prediction", query: "free pick em contest prize money no wager no deposit" },
  { category: "puzzle", query: "puzzle contest prizes real payout free entry official terms" },
  { category: "puzzle", query: "brain games competition cash prize payout free entry" },
  { category: "iq-test", query: "IQ quiz contest cash prize payout free entry official rules" },
  { category: "iq-test", query: "brain test competition cash prize payout no entry fee" },
  { category: "instant-win", query: "free instant win game cash prize no purchase necessary official rules" },
  { category: "instant-win", query: "scratch game cash prizes free entry payout official terms" },
];

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...corsHeaders, "Content-Type": "application/json" },
  });
}

Deno.serve((req: Request) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });
  if (req.method !== "POST") return json({ error: "Method not allowed" }, 405);

  return withSupabase({ auth: "user" }, async (_req, ctx) => {
    const ownerId = ctx.userClaims?.id;
    if (!ownerId) return json({ error: "Authenticated user identity is missing." }, 401);

    const found: Array<Record<string, unknown>> = [];
    const errors: string[] = [];
    const rejected = { invalid_url: 0, excluded_category: 0, missing_free_entry_evidence: 0, missing_reward_evidence: 0, missing_payout_evidence: 0 };
    let acceptedCandidates = 0;
    const searchStats: Array<{ category: string; query: string; results: number; status: number }> = [];

    // Keep the edge function bounded even when the public search service is slow.
    const discoveryStartedAt = Date.now();
    const maxDiscoveryMs = 55_000;
    const requestTimeoutMs = 6_000;
    const maxResultsPerQuery = 8;

    for (let index = 0; index < SEARCHES.length; index++) {
      if (Date.now() - discoveryStartedAt >= maxDiscoveryMs) {
        errors.push("Discovery time budget reached; remaining searches were skipped.");
        break;
      }
      const search = SEARCHES[index];
      try {
        if (index > 0) await new Promise((resolve) => setTimeout(resolve, 350));
        const endpoint = new URL("https://api.mwmbl.org/api/v1/search/");
        endpoint.searchParams.set("s", search.query);
        const remainingMs = maxDiscoveryMs - (Date.now() - discoveryStartedAt);
        if (remainingMs <= 0) {
          errors.push("Discovery time budget reached; remaining searches were skipped.");
          break;
        }
        const response = await fetch(endpoint, {
          headers: { "Accept": "application/json" },
          signal: AbortSignal.timeout(Math.min(requestTimeoutMs, remainingMs)),
        });
        if (!response.ok) {
          errors.push(`${search.category} (${search.query}): Mwmbl returned ${response.status}`);
          searchStats.push({ category: search.category, query: search.query, results: 0, status: response.status });
          continue;
        }

        const declaredLength = Number(response.headers.get("content-length") || 0);
        if (Number.isFinite(declaredLength) && declaredLength > 1_000_000) {
          errors.push(search.category + ": search response exceeded the 1 MB limit.");
          continue;
        }
        let payload: unknown;
        try {
          const responseText = await readBoundedSearchResponse(response);
          payload = parseBoundedSearchResponse(responseText);
        } catch (error) {
          errors.push(search.category + ": " + String(error).slice(0, 160));
          continue;
        }
        const results = Array.isArray(payload) ? payload.slice(0, maxResultsPerQuery) : [];
        searchStats.push({ category: search.category, query: search.query, results: results.length, status: response.status });
        if (Array.isArray(payload) && payload.length > maxResultsPerQuery) {
          errors.push(search.category + ": result list capped at " + maxResultsPerQuery + " items.");
        }
        if (!Array.isArray(payload)) errors.push(`${search.query}: unexpected response format`);

        for (const item of results) {
          const rawUrl = String(item?.url || "");
          const title = String(Array.isArray(item?.title)
            ? item.title.map((part: { value?: string }) => part.value || "").join("")
            : item?.title || "").trim().slice(0, 160);
          const description = String(Array.isArray(item?.extract)
            ? item.extract.map((part: { value?: string }) => part.value || "").join("")
            : item?.extract || "No reward details provided by search result.").trim().slice(0, 900);
          if (title.length < 2) continue;

          const decision = evaluateCandidate(rawUrl, title, description);
          if (!decision.accepted) {
            rejected[decision.reason]++;
            continue;
          }

          acceptedCandidates++;
          const hostname = new URL(decision.url).hostname.replace(/^www\./, "");
          const payoutMethods = decision.payoutMethods;
          const domainFlags = domainReviewFlags(decision.url);
          const reviewFlags = candidateReviewFlags(title, description);
          found.push({
            owner_id: ownerId,
            title,
            platform: hostname.slice(0, 100),
            url: canonicalOpportunityUrl(decision.url)!,
            category: search.category,
            reward_description: description,
            eligibility: `Payout method hints: ${payoutMethods.join(", ") || "not specified"} (unverified). Due-diligence flags: ${reviewFlags.join(", ") || "no missing details detected by text heuristics"}. Country is not used as an AutoEarn discovery filter. Domain flags: ${domainFlags.join(", ") || "none detected by basic heuristics"}; domain ownership is not verified.`,
            terms_url: "",
            status: "discovered",
            score: 0,
            notes: `Payout method hints: ${payoutMethods.join(", ") || "not specified"}. Payment methods are unverified. Due-diligence flags: ${reviewFlags.join(", ") || "no missing details detected by text heuristics"}. Country is not used as an AutoEarn discovery filter. Domain review flags: ${domainFlags.join(", ") || "none detected by basic heuristics"}. A clean flag result does not prove the site is official. Confirm the organizer, official terms, minimum withdrawal, fees, KYC and automation rules. Never deposit or pay to unlock a prize.\n[DISCOVERY PROVENANCE]\n${JSON.stringify({source: "Mwmbl search", search_query: search.query, discovered_at: new Date().toISOString(), excerpt: description})}`,
          });
        }
      } catch (error) {
        errors.push(`${search.category}: ${String(error).slice(0, 180)}`);
      }
    }

    const unique = mergeDuplicateCandidates(found);
    const diagnostics = {
      accepted_candidates: acceptedCandidates,
      rejected,
      searches: searchStats,
      errors,
    };

    if (!unique.length) {
      return json({
        saved: 0,
        scanned: 0,
        duplicates: 0,
        ...diagnostics,
        message: "No candidate pages found. Search diagnostics are included.",
      });
    }

    // Compare canonical URLs against this owner's existing rows as well as
    // this search batch, so tracking links do not create duplicate records.
    const { data: existingRows, error: existingError } = await ctx.supabase
      .from("opportunities")
      .select("url")
      .eq("owner_id", ownerId);
    if (existingError) return json({ error: existingError.message }, 500);

    const existingKeys = new Set(
      (existingRows || [])
        .map((row: { url: string }) => canonicalOpportunityUrl(String(row.url || "")))
        .filter((url): url is string => Boolean(url)),
    );
    const unseen = unique.filter((row) => !existingKeys.has(String(row.url)));
    const alreadySaved = unique.length - unseen.length;
    const duplicatesWithinBatch = acceptedCandidates - unique.length;
    const duplicates = alreadySaved + duplicatesWithinBatch;

    if (!unseen.length) {
      return json({
        saved: 0,
        scanned: unique.length,
        duplicates,
        duplicates_within_batch: duplicatesWithinBatch,
        already_saved: alreadySaved,
        ...diagnostics,
        message: "All discovered candidates already exist in your list; existing owner reviews were left unchanged.",
      });
    }

    const { data, error } = await ctx.supabase
      .from("opportunities")
      .upsert(unseen, { onConflict: "owner_id,url", ignoreDuplicates: true })
      .select("id");

    if (error) return json({ error: error.message }, 500);
    return json({
      saved: data?.length || 0,
      scanned: unique.length,
      duplicates,
      duplicates_within_batch: duplicatesWithinBatch,
      already_saved: alreadySaved,
      ...diagnostics,
      categories: [...new Set(SEARCHES.map((item) => item.category))],
      message: "Candidates saved for your review. They are not verified offers.",
    });
  })(req);
});
